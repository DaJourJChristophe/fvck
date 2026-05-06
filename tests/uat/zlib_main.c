#include "zlib.h"

int main(void) {
    const char input[] = "hello zlib";
    unsigned long input_len = (unsigned long)(sizeof(input) - 1);

    unsigned char out[128];
    unsigned long out_len = (unsigned long)sizeof(out);

    int rc = compress2(out, &out_len, (const unsigned char*)input, input_len, 6);
    return rc == Z_OK ? 0 : 1;
}

