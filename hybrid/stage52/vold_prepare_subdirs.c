/*
 * Copyright (C) 2017 The Android Open Source Project
 * SPDX-License-Identifier: Apache-2.0
 *
 * The prepare operation from Android vold's vold_prepare_subdirs.cpp,
 * using the Recovery ramdisk's libc, libcutils and libselinux directly.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* C interfaces in the tested ARM64 Bionic ramdisk. */
struct selabel_handle;
struct directory;
struct dirent {
    uint64_t d_ino;
    int64_t d_off;
    unsigned short d_reclen;
    unsigned char d_type;
    char d_name[256];
};

extern int *__errno(void);
extern int close(int fd);
extern struct directory *opendir(const char *path);
extern struct dirent *readdir(struct directory *directory);
extern int closedir(struct directory *directory);
extern int dprintf(int fd, const char *format, ...);
extern int snprintf(char *out, size_t size, const char *format, ...);
extern int strcmp(const char *a, const char *b);
extern unsigned geteuid(void);
extern int open(const char *path, int flags, ...);
extern int fchmod(int fd, unsigned mode);
extern struct selabel_handle *selinux_android_file_context_handle(void);
extern int selabel_lookup(struct selabel_handle *, char **context, const char *path, int type);
extern int selinux_android_context_with_level(const char *, char **, unsigned user, unsigned app);
extern int setfscreatecon(const char *context);
extern int fs_prepare_dir(const char *path, unsigned mode, unsigned uid, unsigned gid);
extern int lgetfilecon(const char *path, char **context);
extern int lsetfilecon(const char *path, const char *context);
extern void freecon(char *context);

enum {
    DE = 1, CE = 2, SYSTEM = 1000, CACHE = 2001, DIRECTORY_ENTRY = 4,
    DIRECTORY_MODE = 0040000, MISSING = 2,
    /* Linux ARM64 open flags. */
    WRITE = 1, CREATE = 0100, APPEND = 02000, NOFOLLOW = 0100000, CLOEXEC = 02000000,
};
static const unsigned no_user = UINT32_MAX;
static int log_fd = 2;

static bool path_error(const char *operation, const char *path) {
    dprintf(log_fd, "%s failed for %s (errno=%d)\n", operation, path, *__errno());
    return false;
}

static bool prepare_dir(struct selabel_handle *labels, const char *path, unsigned mode,
                        unsigned uid, unsigned gid, unsigned user) {
    char *context = NULL;
    char *existing = NULL;
    bool ok = false;
    if (selabel_lookup(labels, &context, path, DIRECTORY_MODE) == 0) {
        if (user != no_user) {
            char *with_level = NULL;
            if (selinux_android_context_with_level(context, &with_level, user, no_user) != 0) {
                path_error("selinux_android_context_with_level", path);
                goto done;
            }
            freecon(context);
            context = with_level;
        }
        if (setfscreatecon(context) != 0) {
            path_error("setfscreatecon", path);
            goto done;
        }
    } else if (*__errno() != MISSING) {
        path_error("selabel_lookup", path);
        goto done;
    }

    if (fs_prepare_dir(path, mode, uid, gid) != 0) {
        path_error("fs_prepare_dir", path);
        goto done;
    }
    if (context) {
        if (lgetfilecon(path, &existing) < 0) {
            path_error("lgetfilecon", path);
            goto done;
        }
        if (strcmp(context, existing) != 0 && lsetfilecon(path, context) != 0) {
            path_error("lsetfilecon", path);
            goto done;
        }
    }
    ok = true;

done:
    freecon(existing);
    freecon(context);
    if (setfscreatecon(NULL) != 0) return path_error("clear fscreate context", path);
    return ok;
}

static bool prepare_under(struct selabel_handle *labels, const char *base, const char *name,
                          unsigned mode, unsigned uid, unsigned gid, unsigned user) {
    char path[512];
    int n = snprintf(path, sizeof(path), "%s/%s", base, name);
    if (n < 0 || (size_t)n >= sizeof(path)) {
        dprintf(log_fd, "Directory path exceeds the buffer under %s\n", base);
        return false;
    }
    return prepare_dir(labels, path, mode, uid, gid, user);
}

static bool prepare_apex_subdirs(struct selabel_handle *labels, const char *misc) {
    char apex[256];
    snprintf(apex, sizeof(apex), "%s/apexdata", misc);
    if (!prepare_dir(labels, apex, 0711, 0, 0, no_user)) return false;
    struct directory *dir = opendir("/data/misc/apexdata");
    if (!dir) return path_error("opendir", "/data/misc/apexdata");
    bool ok = true;
    for (;;) {
        *__errno() = 0;
        struct dirent *entry = readdir(dir);
        if (!entry) {
            if (*__errno()) ok = path_error("readdir", "/data/misc/apexdata");
            break;
        }
        if (entry->d_type != DIRECTORY_ENTRY || entry->d_name[0] == '.') continue;
        if (!prepare_under(labels, apex, entry->d_name, 0771, 0, SYSTEM, no_user)) {
            ok = false;
            break;
        }
    }
    closedir(dir);
    return ok;
}

static bool prepare_user(struct selabel_handle *labels, const char *base, unsigned user,
                         bool internal, bool ce) {
    char path[256], misc[128];
    snprintf(path, sizeof(path), "%s/%s/%u", base, ce ? "user" : "user_de", user);
    snprintf(misc, sizeof(misc), "%s/misc_%s/%u", base, ce ? "ce" : "de", user);
    if (!prepare_dir(labels, path, 0771, SYSTEM, SYSTEM, user) ||
        !prepare_under(labels, misc, "sdksandbox", 0771, SYSTEM, SYSTEM, user)) return false;
    if (!internal) return true;

    const char *required[] = {"vold", "storaged", "rollback"};
    for (size_t i = 0; i < sizeof(required) / sizeof(required[0]); ++i) {
        if (!prepare_under(labels, misc, required[i], 0700, 0, 0, no_user)) return false;
    }
    /* Like upstream vold, errors preparing these optional APEX paths are logged. */
    prepare_under(labels, misc, "apexrollback", 0700, 0, 0, no_user);
    prepare_apex_subdirs(labels, misc);

    if (ce) {
        /* Keep existing checkin contents if the requested metadata cannot be set. */
        if (!prepare_under(labels, misc, "checkin", 0770, SYSTEM, CACHE, user)) return false;
        snprintf(path, sizeof(path), "/data/system_ce/%u", user);
        if (!prepare_under(labels, path, "backup", 0700, SYSTEM, SYSTEM, no_user) ||
            !prepare_under(labels, path, "backup_stage", 0700, SYSTEM, SYSTEM, no_user))
            return false;
    } else {
        snprintf(path, sizeof(path), "/data/misc/profiles/cur/%u", user);
        if (!prepare_dir(labels, path, 0771, SYSTEM, SYSTEM, user)) return false;
    }
    snprintf(path, sizeof(path), "/data/vendor_%s/%u", ce ? "ce" : "de", user);
    if (!ce && !prepare_under(labels, path, "fpdata", 0700, SYSTEM, SYSTEM, no_user))
        return false;
    return prepare_under(labels, path, "facedata", 0700, SYSTEM, SYSTEM, no_user);
}

static bool parse_small_uint(const char *text, unsigned *value) {
    if (!text[0]) return false;
    unsigned number = 0;
    for (size_t i = 0; text[i]; ++i) {
        if (i == 6 || text[i] < '0' || text[i] > '9') return false;
        number = number * 10 + (unsigned)(text[i] - '0');
    }
    *value = number;
    return true;
}

static bool valid_volume(const char *uuid) {
    for (size_t i = 0; uuid[i]; ++i) {
        char c = uuid[i];
        if (i == 39 || !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') ||
                         (c >= 'A' && c <= 'F') || c == '-' || c == '_'))
            return false;
    }
    return true;
}

int main(int argc, char **argv, char **env) {
    (void)env;
    if (argc == 2 && !strcmp(argv[1], "--check")) {
        dprintf(1, "Turner Recovery prepare helper ready\n");
        return 0;
    }
    unsigned user, flags;
    if (argc != 5 || strcmp(argv[1], "prepare") || !valid_volume(argv[2]) ||
        !parse_small_uint(argv[3], &user) || !parse_small_uint(argv[4], &flags) ||
        !flags || (flags & ~(DE | CE)) || geteuid() != 0) {
        dprintf(2, "Usage: vold_prepare_subdirs prepare <volume_uuid> <user_id> <flags>\n");
        return 1;
    }
    int fd = open("/tmp/turner-vold-prepare.log", WRITE | CREATE | APPEND | NOFOLLOW | CLOEXEC, 0644);
    if (fd >= 0) {
        log_fd = fd;
        fchmod(fd, 0644);
    }
    char base[64];
    bool internal = !argv[2][0];
    if (internal) {
        snprintf(base, sizeof(base), "/data");
    } else {
        snprintf(base, sizeof(base), "/mnt/expand/%s", argv[2]);
    }
    dprintf(log_fd, "prepare user=%u flags=%u started\n", user, flags);
    struct selabel_handle *labels = selinux_android_file_context_handle();
    if (!labels) path_error("selinux_android_file_context_handle", base);
    bool ok = labels &&
              (!(flags & DE) || prepare_user(labels, base, user, internal, false)) &&
              (!(flags & CE) || prepare_user(labels, base, user, internal, true));
    dprintf(log_fd, "prepare user=%u flags=%u exit=%d\n", user, flags, !ok);
    if (fd >= 0) close(fd);
    return !ok;
}
