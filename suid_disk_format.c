#include <stdio.h>
#include <asm/errno.h>
#include <errno.h>

#define PATH "/opt/idepositbox/id_client/security/format_block_device.py"

int main(int argc, char **argv, char **envp)
{
    *envp = "PYTHONPATH=/opt/idepositbox/";
    execve(PATH, argv, envp);

    if (errno == 2) {
        printf("Path %s does not found!\n", PATH);
    } else {
        printf("ERROR = %d!\n", errno);
    }
}
