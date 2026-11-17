/* spawn_hal v2 (v2.7.1) — generic direct launcher for recovery HALs.
 * Static aarch64 binary, a7/Skyward-style service spawn:
 *   setsid, uid/gid/groups from argv, stdout/stderr -> /dev/kmsg
 *   (opened BEFORE the privilege drop), stdin <- /dev/null,
 *   env: LD_LIBRARY_PATH + LD_PRELOAD passed through verbatim.
 * Usage: spawn_hal <logfile> <uid> <gid> <groups-csv> <ldpath>
 *        <ldpreload|-> <binary> [args...]
 * The parent writes ONE status line to <logfile> and also echoes it to
 * its own stderr (which turner-setup routes to /dev/kmsg), so the spawn
 * outcome is visible in dmesg even if /tmp writes fail:
 *   "spawn_hal: <binary> pid <pid>"        fork succeeded
 *   "spawn_hal: OPENLOG FAIL <logfile>"    logfile could not be opened
 *   "spawn_hal: FORK FAIL"                 fork failed
 * v1 (shipped in v2.6/v2.7) returned 0 unconditionally and setup read an
 * empty pid for all three HALs while no child output ever reached
 * kmsg — the launcher path itself was never verified end-to-end. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <grp.h>
#include <sys/types.h>

int main(int argc, char **argv) {
    if (argc < 9) { dprintf(2, "spawn_hal: argc<9\n"); return 2; }
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

    int kmsg = open("/dev/kmsg", O_WRONLY);

    pid_t pid = fork();
    if (pid < 0) {
        dprintf(2, "spawn_hal: FORK FAIL for %s\n", binargv[0]);
        return 1;
    }
    if (pid > 0) {
        char line[512];
        int n = snprintf(line, sizeof(line), "spawn_hal: %s pid %d\n",
                         binargv[0], (int)pid);
        FILE *f = fopen(logf, "a");
        if (f) { fputs(line, f); fclose(f); }
        else dprintf(2, "spawn_hal: OPENLOG FAIL %s\n", logf);
        if (n > 0) write(2, line, (size_t)n);
        return 0;
    }
    setsid();
    if (kmsg >= 0) { dup2(kmsg, 1); dup2(kmsg, 2); }
    int dn = open("/dev/null", O_RDONLY);
    if (dn >= 0) dup2(dn, 0);
    setgroups(ngroups, groups);
    setgid(gid);
    setuid(uid);
    static char env_ld[1200], env_pre[600];
    snprintf(env_ld, sizeof(env_ld), "LD_LIBRARY_PATH=%s", ldpath);
    snprintf(env_pre, sizeof(env_pre), "LD_PRELOAD=%s", ldpreload);
    static char *envp[5];
    int ei = 0;
    envp[ei++] = env_ld;
    if (strcmp(ldpreload, "-") != 0) envp[ei++] = env_pre;
    envp[ei++] = "PATH=/system/bin";
    envp[ei] = NULL;
    execve(binargv[0], binargv, envp);
    dprintf(2, "spawn_hal: execve %s FAILED\n", binargv[0]);
    _exit(127);
}
