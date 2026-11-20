// SPDX-License-Identifier: Apache-2.0
// Read-only KMS inspection; no DRM master, modeset, or framebuffer writes.
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <unistd.h>
struct resources { uint64_t fbs, crtcs, connectors, encoders; uint32_t nf,nc,nn,ne,minw,maxw,minh,maxh; };
struct mode { uint32_t clock; uint16_t hd,hs,he,ht,hsk,vd,vs,ve,vt,vscan; uint32_t refresh,flags,type; char name[32]; };
struct connector { uint64_t encoders,modes,props,values; uint32_t nm,np,ne,encoder,id,type,type_id,connected,width,height,subpixel,pad; };
struct crtc { uint64_t connectors; uint32_t count,id,fb,x,y,gamma,valid; struct mode mode; };
_Static_assert(sizeof(struct mode)==68,"mode");
_Static_assert(sizeof(struct crtc)==104,"crtc");
int main(void) {
    int fd=open("/dev/dri/card0",O_RDONLY|O_CLOEXEC); if(fd<0){perror("open");return 1;}
    struct resources r={0};if(ioctl(fd,0xc04064a0,&r)){perror("resources");return 1;}
    if(r.nc>64||r.nn>64)return 1;
    uint32_t cs[64],ns[64];r.crtcs=(uintptr_t)cs;r.connectors=(uintptr_t)ns;r.nf=r.ne=0;
    if(ioctl(fd,0xc04064a0,&r))return 1;
    for(unsigned i=0;i<r.nc;i++){struct crtc c={.id=cs[i]};if(!ioctl(fd,0xc06864a1,&c))printf("CRTC %u valid=%u fb=%u mode=%ux%u@%u\n",c.id,c.valid,c.fb,c.mode.hd,c.mode.vd,c.mode.refresh);}
    for(unsigned i=0;i<r.nn;i++){
        struct mode m[128];uint32_t es[64],ps[128];uint64_t vs[128];
        struct connector c={.id=ns[i],.nm=128,.np=128,.ne=64,.modes=(uintptr_t)m,.encoders=(uintptr_t)es,.props=(uintptr_t)ps,.values=(uintptr_t)vs};
        if(ioctl(fd,0xc05064a7,&c)||c.nm>128)return 1;
        printf("CONNECTOR %u connected=%u modes=%u\n",c.id,c.connected,c.nm);
        for(unsigned j=0;j<c.nm;j++)printf("  %u %ux%u@%u clock=%u flags=%x type=%x\n",j,m[j].hd,m[j].vd,m[j].refresh,m[j].clock,m[j].flags,m[j].type);
    }
    close(fd);return 0;
}
