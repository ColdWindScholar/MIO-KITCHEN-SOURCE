# bootio #

The bootio tool records I/O for processes during boot.
To use bootio kernel must be compiled with this flags:

    CONFIG_TASKSTATS=y
    CONFIG_TASK_DELAY_ACCT=y
    CONFIG_TASK_XACCT=y
    CONFIG_TASK_IO_ACCOUNTING=y

To use bootio make sure it's included in product config for the board.
Create file /data/misc/bootio/start with a command like the following:

    adb shell 'echo "$TIMEOUT $SAMPLES" > /data/misc/bootio/start'

Where the value of $TIMEOUT corresponds to the desired bootio period in
seconds and $SAMPLES corresponds to the desired number of samples.

Note: /data/misc/bootio/start is not deleted automatically, so don't
forget to delete it when you're done collecting data.

To see collected logs run:

    adb shell bootio -p
