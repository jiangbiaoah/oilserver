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

$ cd server_comm  # 切换到nohup.out所在的目录

$ tail -f nohup.out     # 实时显示服务器日志

## 文档结构如下
server_comm：主目录，相关代码均在这里
- config.py : 服务器的配置文件，此配置文件用于本地测试
- config_server.py : 服务器的配置文件，部署到实际生产环境中时，将其名称改为config.py
- start_service.py : 开启服务器模块，服务器端主逻辑模块
- stop_service.py : 关闭服务器模块
- data_process.py : 数据处理子模块
- sqloperate.py : 数据库相关操作子模块

virtual_devoce: 该目录下存储仿真的井设备，供测试使用
- virtual_device.py : 虚拟的设备

oilappserver.sh: 脚本：功能为打开/关闭/重启服务器