// SPDX-License-Identifier: Apache-2.0
// Keep installed-ROM HALs alive independently of writable Super partitions.
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <sched.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/system_properties.h>
#include <unistd.h>

static const char *pidfile = "/tmp/turner-runtime/namespace.pid";
static int fail(const char *s) {
    int error = errno;
    FILE *log = fopen("/tmp/turner-runtime/errors.log", "ae");
    if (log) { fprintf(log, "pid=%d %s: %s\n", getpid(), s, strerror(error)); fclose(log); }
    errno=error; perror(s); return 1;
}
int main(int argc, char **argv) {
    const char *name = strrchr(argv[0], '/');
    name = name ? name + 1 : argv[0];
    if (!strcmp(name, "bootctl")) {
        // The stock MTK service speaks the stock ramdisk Binder ABI. Do not
        // inherit recovery GUI SDK35 or an installer's older C++ libraries.
        unsetenv("LD_LIBRARY_PATH");
        unsetenv("LD_PRELOAD");
        execv("/system/bin/turner-bootctl-real", argv);
        return fail("exec stock-ABI bootctl");
    }
    if (!strcmp(name, "ziptool") || !strcmp(name, "unzip") || !strcmp(name, "zipinfo")) {
        unsetenv("LD_PRELOAD");
        setenv("LD_LIBRARY_PATH","/system/lib64/turner-stream:/system/lib64/twrp16:/system/lib64",1);
        execv("/system/bin/turner-ziptool-real", argv);
        return fail("exec bounded ZIP64 extractor");
    }
    if (argc == 2 && !strcmp(argv[1], "hold")) {
        if (unshare(CLONE_NEWNS)) return fail("unshare runtime mounts");
        if (mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL))
            return fail("make runtime mounts private");
        FILE *f = fopen(pidfile, "we");
        if (!f) return fail("open namespace pidfile");
        fprintf(f, "%d\n", getpid());
        if (fclose(f)) return fail("save namespace pidfile");
        __system_property_set("vendor.turner.runtime.namespace", "ready");
        // Crypto uses /metadata, persist and its RAM keystore. These mounts
        // exist before this keeper starts. Never remount changed Super here.
        for (;;) pause();
    }
    if (argc >= 3 && !strcmp(argv[1], "enter")) {
        char state[PROP_VALUE_MAX] = {0};
        __system_property_get("vendor.turner.runtime.namespace", state);
        if (strcmp(state, "ready")) {
            fprintf(stderr, "Turner runtime namespace is not ready\n");
            return 1;
        }
        FILE *f = fopen(pidfile, "re");
        int pid = 0;
        if (!f || fscanf(f, "%d", &pid) != 1 || pid <= 1) return fail("read namespace PID");
        fclose(f);
        char path[128], exe[256];
        snprintf(path, sizeof(path), "/proc/%d/exe", pid);
        ssize_t n = readlink(path, exe, sizeof(exe)-1);
        if (n < 0) return fail("read keeper executable");
        exe[n] = 0;
        if (strcmp(exe, "/system/bin/turner-runtime")) {
            fprintf(stderr, "Unexpected runtime keeper executable\n");
            return 1;
        }
        snprintf(path, sizeof(path), "/proc/%d/ns/mnt", pid);
        int fd = open(path, O_RDONLY | O_CLOEXEC);
        if (fd < 0 || setns(fd, CLONE_NEWNS)) return fail("enter runtime mounts");
        close(fd);
        execv(argv[2], argv + 2);
        return fail("exec runtime service");
    }
    fprintf(stderr, "usage: turner-runtime hold | enter /absolute/program [args...]\n");
    return 64;
}
