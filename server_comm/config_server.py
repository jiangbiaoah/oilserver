# -*- coding: UTF-8 -*-
import logging

# MYSQL配置
sql_host = "localhost"
sql_username = "root"
sql_password = "W.w000000"
database_name = "oilapp_niuqun"

# 服务器端Socket配置：外网
server_ip = '0.0.0.0'
server_port = 41234

# 服务器端Socket配置：内网
# server_ip = '192.168.131.105'
# server_port = 41234

# logging日志配置
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

data_len = 28       # 协议字段长度，以此判断接收到的数据是否正确
# data_len_version_1 # 第一版帧格式的长度为19,固化在代码中了
control_len = 19    # 控制帧字节长度，以判断接收到的控制命令是否正确

