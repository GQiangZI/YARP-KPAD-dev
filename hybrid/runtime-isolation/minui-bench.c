// SPDX-License-Identifier: Apache-2.0
// Run only with recovery stopped, under an independent init-owned watchdog.
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void *sym(void *h,const char *n){void *p=dlsym(h,n);if(!p){fprintf(stderr,"%s: %s\n",n,dlerror());exit(2);}return p;}
int main(int argc,char **argv){
    alarm(20);setbuf(stdout,NULL);if(argc!=2)return 2;
    void *h=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!h){fprintf(stderr,"%s\n",dlerror());return 2;}
    int (*init)(void)=sym(h,"_Z7gr_initv");
    void (*finish)(void)=sym(h,"_Z7gr_exitv");
    void (*flip)(void)=sym(h,"_Z7gr_flipv");
    int (*blit)(const void*,int,int,int,int,int)=sym(h,"_Z11gr_blit_rawPKviiiii");
    int (*width)(void)=sym(h,"_Z11gr_fb_widthv");
    int (*height)(void)=sym(h,"_Z12gr_fb_heightv");
    if(init()){fprintf(stderr,"gr_init failed\n");return 3;}
    printf("BENCH initialized width=%d height=%d\n",width(),height());
    unsigned char *pixels=malloc((size_t)width()*height()*4);if(!pixels)return 4;
    for(size_t j=0;j<(size_t)width()*height()*4;j++)pixels[j]=(j%4==3)?255:20;
    for(int kind=0;kind<2;kind++){double draw=0,present=0,max=0;
        for(int i=0;i<35;i++){
            double a=now();
            int w=kind?width()/2:width(),hh=kind?height()/4:height();
            if(blit(pixels,w,hh,w*4,0,0)<0)return 5;
            double b=now();flip();double c=now();
            if(i>=5){draw+=b-a;present+=c-b;if(c-a>max)max=c-a;}
        }
        printf("BENCH %s draw_ms=%.3f present_ms=%.3f total_ms=%.3f fps=%.2f worst_ms=%.3f\n",kind?"partial":"full",draw*1000/30,present*1000/30,(draw+present)*1000/30,30/(draw+present),max*1000);
    }
    free(pixels);finish();dlclose(h);return 0;
}
