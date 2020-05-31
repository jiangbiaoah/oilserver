#!/bin/sh
#
workdir=server_comm

server_start(){
    cd $workdir
    nohup python3 start_service.py &
}
server_stop(){
    pid=`ps -ef | grep 'python3 start_service.py' | awk '{ print $2 }'`
    echo $pid
    kill $pid
    sleep 2
    echo "Server Killed."
    cd $workdir
    python3 stop_service.py
}
case "$1" in
    start)
        server_start
        ;;
    stop)
        server_stop
        ;;
    restart)
        server_stop
        server_start
        ;;
    *)
    echo "Usage: Services {start|stop|restart}"
    exit 1
esac
exit 0
