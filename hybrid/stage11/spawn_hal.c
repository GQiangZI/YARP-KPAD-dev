/* spawn_hal — generic direct launcher for recovery HALs (v2.6).
 * Static aarch64 binary. Mirrors the Skyward/a7 service definition:
 *   setsid, uid/gid/groups from argv, /dev/kmsg opened BEFORE the
 *   privilege drop (v2.5's spawn_touch opened it after setuid, the open
 *   failed, and the HAL's stderr went nowhere — fixed here),
 *   stdout/stderr -> /dev/kmsg, stdin <- /dev/null,
 *   env: LD_LIBRARY_PATH + LD_PRELOAD passed through verbatim.
 * Usage: spawn_hal <logfile> <uid> <gid> <groups-csv> <ldpath> <ldpreload|->
 *        <binary> [args...]
 * Parent writes the child pid to <logfile> and exits 0. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <grp.h>
#include <sys/types.h>

int main(int argc, char **argv) {
    if (argc < 9) return 2;
    const char *logf = argv[1];
    uid_t uid = (uid_t)atoi(argv[2]);
    gid_t gid = (gid_t)atoi(argv[3]);
    gid_t groups[16]; int ngroups = 0;
    char gbuf[256]; strncpy(gbuf, argv[4], sizeof(gbuf) - 1); gbuf[sizeof(gbuf) - 1] = 0;
    for (char *tok = strtok(gbuf, ","); tok && ngroups < 16; tok = strtok(NULL, ","))
        groups[ngroups++] = (gid_t)atoi(tok);
    const char *ldpath = argv[5];
    const char *ldpreload = argv[6];
    char **binargv = &argv[7];

    /* Open kmsg as root, before forking, so the fd survives the drop. */
    int kmsg = open("/dev/kmsg", O_WRONLY);

    pid_t pid = fork();
    if (pid < 0) return 1;
    if (pid > 0) {
        FILE *f = fopen(logf, "a");
        if (f) { fprintf(f, "spawn_hal: %s pid %d\n", binargv[0], (int)pid); fclose(f); }
        return 0;
    }
    setsid();
    if (kmsg >= 0) { dup2(kmsg, 1); dup2(kmsg, 2); }
    int dn = open("/dev/null", O_RDONLY);
    if (dn >= 0) dup2(dn, 0);
    setgroups(ngroups, groups);
    setgid(gid);
    setuid(uid);
    char env_ld[1200], env_pre[600];
    snprintf(env_ld, sizeof(env_ld), "LD_LIBRARY_PATH=%s", ldpath);
    snprintf(env_pre, sizeof(env_pre), "LD_PRELOAD=%s", ldpreload);
    static char *envp[5];
    int ei = 0;
    envp[ei++] = env_ld;
    if (strcmp(ldpreload, "-") != 0) envp[ei++] = env_pre;
    envp[ei++] = "PATH=/system/bin";
    envp[ei] = NULL;
    execve(binargv[0], binargv, envp);
    dprintf(2, "spawn_hal: execve %s failed\n", binargv[0]);
    _exit(127);
}
