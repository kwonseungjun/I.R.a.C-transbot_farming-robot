
#include <string>
#include <boost/version.hpp>

#include "mongo/util/version.h"

namespace mongo {
    const char * gitVersion() { return "19b8664f41ff0d8e198d8a9aacec4376bab0ac9e"; }
    const char * compiledJSEngine() { return "V8"; }
    const char * allocator() { return "None"; }
    const char * loaderFlags() { return "-fPIC -pthread -Wl,-z,now -rdynamic"; }
    const char * compilerFlags() { return "-Wnon-virtual-dtor -Woverloaded-virtual -fPIC -fno-strict-aliasing -ggdb -pthread -Wall -Wsign-compare -Wno-unknown-pragmas -Winvalid-pch -pipe -O3 -Wno-unused-local-typedefs -Wno-unused-function -Wno-deprecated-declarations -Wno-unused-const-variable -fno-builtin-memcmp"; }
    std::string sysInfo() { return "Linux jetson-yahboom 4.9.201-tegra #1 SMP PREEMPT Fri Feb 19 08:40:32 PST 2021 aarch64 BOOST_LIB_VERSION=" BOOST_LIB_VERSION ; }
}  // namespace mongo
