#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "PosterBoardLSStoreCore.h"
#define CAP (128u*1024u)
static void u32(uint8_t *p,uint32_t n) {
    for(int i=0;i<4;++i)p[i]=(uint8_t)(n>>(8*i));
}
static size_t put_string(uint8_t *b,size_t off,uint32_t id,const char *v) {
    size_t n=strlen(v);assert(off+8+n+4<CAP);
    u32(b+off,id);u32(b+off+4,(uint32_t)n);
    memcpy(b+off+8,v,n);
    return (off+8+n+3)&~(size_t)3;
}
static void put_record(uint8_t *b,size_t off,uint32_t idref,uint32_t pathref,int variant){
    uint32_t size=variant?0x250:0x25c;
    u32(b+off+4,size);
    u32(b+off+8+(variant?0x0c:0x0c),idref);
    u32(b+off+8+(variant?0x68:0x6c),pathref);
}
static uint8_t* make_store(bool posterboard,bool duplicate,bool wrongLayout){
    uint8_t *b=calloc(CAP,1);assert(b);memcpy(b,"bdsl",4);
    size_t start=0x8500;
    start=put_string(b,start,100,"com.apple.PosterBoard");
    start=put_string(b,start,101,"com.apple.mobilesafari");
    const char *a="/private/var/mobile/Containers/Data/Application/";
    for(int i=0;i<32;i++){
        char s[160];snprintf(s,sizeof(s),"%s%08X-0000-4000-8000-%012X",a,(unsigned)i+1,(unsigned)i+1);
        start=put_string(b,start,200+i,s);
        put_record(b,0x200+i*0x268,(posterboard&&i==7)?(100u<<2):(101u<<2),
                   (uint32_t)(200+i)<<2,wrongLayout);
    }
    if(duplicate) {
        put_record(b,0x200+32*0x268,100u<<2,201u<<2,wrongLayout);
    }
    return b;
}
int main(void) {
    uint8_t *b=make_store(true,false,false);
    PBLSResult r=pbls_parse(b,CAP);
    assert(r.verified&&r.layoutScore>=32&&r.recordsMatched==1);
    assert(strstr(r.container,"00000008-0000-4000-8000-000000000008"));
    puts("PASS: exact PosterBoard identity maps to verified data container");
    memset(b,0,16);r=pbls_parse(b,CAP);assert(!r.verified);
    puts("PASS: non-CSStore magic rejected");
    free(b);
    b=make_store(false,false,false);r=pbls_parse(b,CAP);assert(!r.verified);
    puts("PASS: no PosterBoard identity rejected");
    free(b);
    b=make_store(true,true,false);r=pbls_parse(b,CAP);assert(!r.verified&&r.conflicting>0);
    puts("PASS: conflicting PosterBoard UUIDs rejected");
    free(b);
    b=make_store(true,false,true);r=pbls_parse(b,CAP);assert(r.verified);
    puts("PASS: earlier iOS bundle layout accepted when independently supported");
    free(b);
    b=make_store(true,false,false);
    // Invalid UUID: corrupt the exact PosterBoard path; parser must refuse it.
    char *hit=(char*)memmem(b,CAP,"00000008-0000-4000-8000-000000000008",36);
    assert(hit);hit[9]='X';r=pbls_parse(b,CAP);assert(!r.verified);
    puts("PASS: malformed UUID rejected");
    free(b);
    b=make_store(true,false,false);
    r=pbls_parse(b,300);assert(!r.verified);
    r=pbls_parse(b,(size_t)PBLS_MAX_BYTES+1);assert(!r.verified);
    puts("PASS: truncated and oversized stores rejected");
    free(b);
    puts("PASS: 7 independent CSStore identity and layout tests");
    return 0;
}
