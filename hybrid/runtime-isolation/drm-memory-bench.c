// SPDX-License-Identifier: Apache-2.0
// Allocate private dumb buffers only: no master, modeset or active FB access.
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
struct dumb { uint32_t height,width,bpp,flags,handle,pitch; uint64_t size; };
struct mapping { uint32_t handle,pad; uint64_t offset; };
struct cap { uint64_t capability,value; };
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return t.tv_sec+t.tv_nsec/1e9; }
static void measure(const char *name, void *dst, const void *src, size_t n) {
    double start=now();
    for(int i=0;i<12;i++) { memcpy(dst,src,n); __asm__ __volatile__("" ::: "memory"); }
    double ms=(now()-start)*1000/12;
    printf("%s bytes=%zu mean_ms=%.3f MiB_per_s=%.1f\n",name,n,ms,n/(1024.0*1024.0)/(ms/1000));
    fflush(stdout);
}
int main(void) {
    alarm(25);
    int fd=open("/dev/dri/card0",O_RDWR|O_CLOEXEC); if(fd<0){perror("open");return 1;}
    struct cap c={.capability=4}; if(!ioctl(fd,_IOWR('d',0x0c,struct cap),&c)) printf("prefer_shadow=%llu\n",(unsigned long long)c.value);
    struct dumb d[2]={{.height=3008,.width=1880,.bpp=32},{.height=3008,.width=1880,.bpp=32}};
    void *p[2];
    for(int i=0;i<2;i++){
        if(ioctl(fd,_IOWR('d',0xb2,struct dumb),&d[i])){perror("create");return 1;}
        struct mapping m={.handle=d[i].handle};
        if(ioctl(fd,_IOWR('d',0xb3,struct mapping),&m)){perror("map");return 1;}
        p[i]=mmap(NULL,d[i].size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,m.offset);
        if(p[i]==MAP_FAILED){perror("mmap");return 1;}
        memset(p[i],0x28,d[i].size);
    }
    void *ram=malloc(d[0].size), *ram2=malloc(d[0].size);
    if(!ram||!ram2)return 1;
    memset(ram,0x35,d[0].size);memset(ram2,0x45,d[0].size);
    measure("RAM_to_RAM",ram2,ram,d[0].size);
    measure("RAM_to_DRM",p[0],ram,d[0].size);
    measure("DRM_to_RAM",ram,p[0],d[0].size);
    measure("DRM_to_DRM",p[1],p[0],d[0].size);
    for(int i=0;i<2;i++){munmap(p[i],d[i].size);ioctl(fd,_IOWR('d',0xb4,uint32_t),&d[i].handle);}
    free(ram);free(ram2);close(fd);return 0;
}
