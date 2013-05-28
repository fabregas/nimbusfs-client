#include <stdio.h>
#include <asm/errno.h>
#include <errno.h>

#define PATH "/opt/idepositbox/{RELPATH}"

int main(int argc, char **argv, char **envp)
{
    *envp = "PYTHONPATH=/opt/idepositbox/";
    int egid = 0, uid = 0;
    if (setegid(egid) == -1)
    {
        fprintf(stderr, "Could not set the EGID to %d.  errno=%d\n", egid, errno);
        exit(1);
    }
    if (setuid(uid) == -1)
    {
        fprintf(stderr, "Could not set the UID to %d.  errno=%d\n", egid, errno);
        exit(1);
    }
    execve(PATH, argv, envp);

    if (errno == 2) {
        fprintf(stderr, "Path %s does not found!\n", PATH);
    } else {
        fprintf(stderr, "ERROR = %d!\n", errno);
    }
}
