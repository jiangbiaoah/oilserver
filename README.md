# oilserver
oilapp服务器端

## Shell脚本oilappserver.sh
脚本功能：打开/关闭/重启服务器

注：把该脚本文件放在项目文件相同的目录下


### 打开/关闭/重启服务器的命令如下：
$ sh oilappserver.sh start

$ sh oilappserver.sh stop

$ sh oilappserver.sh restart

## 查看实时日志
开启服务器后，日志文件保存在了nohup.out中，使用如下命令查看实时日志：

$ tail -f nohup.out