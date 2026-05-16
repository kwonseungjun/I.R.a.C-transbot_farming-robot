#include <time.h>
int main()
{
#ifndef timegm
    (void) timegm;
#endif
    ;
    return 0;
}
