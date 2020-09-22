#!/bin/sh
# 该脚本需要放在项目目录下，即/server_comm/logsplit.sh，而不是根目录
cd /root/server_comm

logfold="logfold"
if [ ! -d "$logfold" ]; then
  mkdir "./$logfold"
fi

folder=`date +"%Y-%m"`
if [ ! -d "./$logfold/$folder" ]; then
  mkdir "./$logfold/$folder"
fi

yesterday=`date -d "1 day ago" +"%Y%m%d"`
logfilename="log_$yesterday"

cp ./nohup.out ./$logfold/$folder/$logfilename
cat /dev/null > nohup.out
