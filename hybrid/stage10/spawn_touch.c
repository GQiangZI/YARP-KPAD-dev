/* spawn_touch — v2.5 leg 1 helper: launch the Xiaomi touch HAL the a7
 * (Skyward) way, as a plain detached process instead of an init service.
 * Static aarch64 binary; no libc runtime deps beyond syscalls.
 * Usage: spawn_touch <logfile>
 * Fixed contract (a7 device.toml, touch [[service]]):
 *   uid 1000 (system), gids 1000 (system) + 1004 (input), setsid,
 *   stdout/stderr -> /dev/kmsg (init services swallow stderr; kmsg is
 *   the whole point — the HAL's own words land in dmesg),
 *   env LD_LIBRARY_PATH (ramdisk-first) + LD_PRELOAD libkmsglog,
 *   exec /odm/bin/hw/vendor.xiaomi.hw.touchfeature-service.
 * Prints the child pid to <logfile> (append) and exits immediately. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <grp.h>

int main(int argc, char **argv) {
    const char *logf = argc > 1 ? argv[1] : "/tmp/touchhal.log";
    pid_t pid = fork();
    if (pid < 0) return 1;
    if (pid > 0) {
        FILE *f = fopen(logf, "a");
        if (f) { fprintf(f, "spawn_touch: child pid %d\n", (int)pid); fclose(f); }
        return 0;
    }
    /* child */
    setsid();
    gid_t groups[2] = {1000, 1004};
    setgroups(2, groups);
    setgid(1000);
    setuid(1000);
    int k = open("/dev/kmsg", O_WRONLY);
    if (k >= 0) { dup2(k, 1); dup2(k, 2); if (k > 2) close(k); }
    int dn = open("/dev/null", O_RDONLY);
    if (dn >= 0) { dup2(dn, 0); if (dn > 2) close(dn); }
    static char *envp[] = {
        "LD_LIBRARY_PATH=/system/lib64:/system/lib64/bootstrap:/mnt/system/system/lib64:/mnt/system/system/lib64/bootstrap:/apex/com.android.i18n/lib64:/apex/com.android.runtime/lib64:/apex/com.android.runtime/lib64/bionic:/odm/lib64:/vendor/lib64:/mnt/system_ext/lib64",
        "LD_PRELOAD=/system/etc/hybrid/libkmsglog.so",
        "PATH=/system/bin:/system/xbin",
        NULL
    };
    char *args[] = { "vendor.xiaomi.hw.touchfeature-service", NULL };
    execve("/odm/bin/hw/vendor.xiaomi.hw.touchfeature-service", args, envp);
    dprintf(2, "spawn_touch: execve touchfeature failed\n");
    _exit(127);
}
