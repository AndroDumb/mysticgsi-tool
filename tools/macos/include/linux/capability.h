/* Linux capability xattr wire format used by the Android image builder.
 * These are image metadata, not capabilities of the macOS host.
 */
#ifndef MYSTIC_LINUX_CAPABILITY_H
#define MYSTIC_LINUX_CAPABILITY_H
#include <stdint.h>
#define CAP_SETGID 6
#define CAP_SETUID 7
#define CAP_BLOCK_SUSPEND 36
#define VFS_CAP_REVISION_2 0x02000000
#define VFS_CAP_FLAGS_EFFECTIVE 0x000001
struct vfs_cap_data {
    uint32_t magic_etc;
    struct {
        uint32_t permitted;
        uint32_t inheritable;
    } data[2];
};
#endif
