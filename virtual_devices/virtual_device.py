# -*- coding: UTF-8 -*-

import socket
import datetime
import time
import threading
from decimal import Decimal


host = '111.229.127.107'    # 服务器
# host = '192.168.131.105'  # 表示device
# host = 'Tigerkin'
port = 41234

mutex = threading.Lock()
# 设备初始信息
device_data = {}
device_data['wellid'] = b'\x58\x02\x00\x00'
device_data['reporttime'] = (0, 0)
device_data['acstate'] = 1  # 交流是否有电
device_data['batlow'] = 0  # 电池是否电量低
device_data['wellstate'] = 1  # 开/关井状态
device_data['model'] = 0  # 自动/手动模式
device_data['manual_switch_state'] = 0  # 手动开关状态
device_data['nowcurrent'] = (1, 2)  # 当前电流信息
device_data['upcurrent'] = (30, 6)  # 上死点电流信息
device_data['lowcurrent'] = (29, 4)  # 下死点电流信息
device_data['bell_exception'] = 0  # 曲柄销子
device_data['oil_pressure'] = (1, 0)  # 油压
device_data['tao_pressure'] = (1, 0)  # 套压
device_data['hui_pressure'] = (1, 0)  # 回压


class DeviceThread(threading.Thread):
    def __init__(self, sock, type='send'):
        threading.Thread.__init__(self)
        self.sock = sock
        self.type = type

    def run(self):
        if self.type is 'send':
            print("[开启device发送线程.]")
            send_thread(self.sock)
        elif self.type is 'rec':
            print("[开启device接收线程.]")
            rec_thread(self.sock)
        else:
            pass


def send_thread(sock):
    while True:
        start_time = time.time()
        print("")
        print("[ 当前时间：{} ]".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        data_send = _get_device_data()
        # data_send = b'\xaa\xaa\x0f\x00\x00\x01\x01\x00\x01\x00\x04\x00\x00\x00\x00\x00UU'

        sock.send(data_send)
        print("已向服务器发送数据：{}".format(data_send))
        # time.sleep(600)
        # 发送心跳包
        while True:
            end_time = time.time()
            interval = Decimal(end_time - start_time).quantize(Decimal('0.00'))
            INT = 60 * 10
            if interval < INT:
                time.sleep(30)
                sock.send(b'\xcc\xcc\x00')      # 心跳包
                print("发送心跳包b\xcc\xcc\x00 ({} < {})".format(interval, INT))
                continue
            break


def rec_thread(sock):
    while True:
        print("")
        print("[ 当前时间：{} ]".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        print("准备接收数据...")
        data_rec = sock.recv(1024)
        print("收到数据：{}".format(data_rec))
        _change_state(data_rec)

        # 收到控制命令后立即上报
        data_send = _get_device_data()
        sock.send(data_send)
        print("已立即上报数据：{}".format(data_send))


def _change_state(data_control):
    """
    收到微信的控制命令后，模拟更新设备状态device_data
    :param data_control:
    :return:
    """
    data_dict = _decode_data_rec(data_control)
    function_code = data_dict['function_code']
    print("收到的控制命令为：")

    if function_code == 0 or function_code == 1:    # 开关井定时打开/关闭
        start = "{}:{}".format(data_dict['open_time'][0], data_dict['open_time'][1])
        end = "{}:{}".format(data_dict['close_time'][0], data_dict['close_time'][1])
        if function_code == 0:
            print("======================================")
            print("== 打开定时开关井   定时：{} - {}".format(start, end))
            print("======================================")
        if function_code == 1:
            print("======================================")
            print("== 关闭定时开关井   定时：{} - {}".format(start, end))
            print("======================================")

    if function_code == 2 or function_code == 3:    # 间隔上报打开/关闭
        interval = "{}:{}".format(data_dict['time_interval_timer'][0], data_dict['time_interval_timer'][1])
        if function_code == 2:
            print("======================================")
            print("== 打开间隔上报     间隔：{}".format(interval))
            print("======================================")
        if function_code == 3:
            print("======================================")
            print("== 关闭间隔上报     间隔：{}".format(interval))
            print("======================================")

    if function_code == 4 or function_code == 5:    # 立即开井/关井
        if function_code == 4:
            print("======================================")
            print("==            立即开井                =")
            print("======================================")
        if function_code == 5:
            print("======================================")
            print("==            立即关井                =")
            print("======================================")
        _update_device_state(state=function_code)

    if function_code == 6:      # 设定时间
        current_time = "{}:{}".format(data_dict['current_time'][0], data_dict['current_time'][1])
        print("======================================")
        print("==  设定时间    设置为：{}".format(current_time))
        print("======================================")
        set_time = (data_dict['current_time'][0], data_dict['current_time'][1])
        _update_device_state(set_time=set_time)


def _decode_data_rec(data):
    """
    解析控制命令帧:
    :param data:b'\xaa\xaa\x00\x02\x00\x08\x02\x08\x01\x08\x00\x55\x55'
    :return:dict类型的控制命令data_dict
    """
    # data = b'\xbb\xbb\x58\x02\x00\x00\xaa\xaa\x00\x02\x00\x08\x02\x08\x01\x08\x00\x55\x55'
    # data2device =                  b'\xaa\xaa\x00\x02\x00\x08\x02\x08\x01\x08\x00\x55\x55'
    data_dict = {}
    data_dict['function_code'] = data[2]
    data_dict['time_interval_timer'] = (data[3], data[4])  # (hour, min) 第一个字节单位：时；第二个字节单位：分钟
    data_dict['open_time'] = (data[5], data[6])
    data_dict['close_time'] = (data[7], data[8])
    data_dict['current_time'] = (data[9], data[10])

    return data_dict


def _update_device_state(state=None, set_time=None):
    """
    更新设备状态
    两个状态需要更新：1.开/关井状态  2.设定当前时间
    device_data = b'\xaa\xaa\x58\x02\x00\x00\x08\x00\x01\x00\x01\x00\x02\x0a\x00\x05\x00\x0f\x00\x00\x0a\x00\x0b\x00\x0c\x00UU'
    :return:
    """
    if state is not None:
        # 收到的控制命令中：4表示立即开井,5表示立即关井
        # 上报数据协议帧中：1表示开井状态,5表示关井状态
        if state == 4:
            device_data['wellstate'] = 1
        elif state == 5:
            device_data['wellstate'] = 0

    if set_time is not None:
        device_data['reporttime'] = set_time
        # print("set_time = {}".format(set_time))


def _get_device_data():
    mutex.acquire()
    dict2bytes = [device_data['reporttime'][0], device_data['reporttime'][1],
                  device_data['acstate'], device_data['batlow'],
                  device_data['wellstate'],
                  device_data['model'], device_data['manual_switch_state'],
                  device_data['nowcurrent'][0], device_data['nowcurrent'][1],
                  device_data['upcurrent'][0], device_data['upcurrent'][1],
                  device_data['lowcurrent'][0], device_data['lowcurrent'][1],
                  device_data['bell_exception'],
                  device_data['oil_pressure'][0], device_data['oil_pressure'][1],
                  device_data['tao_pressure'][0], device_data['tao_pressure'][1],
                  device_data['hui_pressure'][0], device_data['hui_pressure'][1]]
    mutex.release()
    data_new = b'\xaa\xaa' + device_data['wellid'] + bytes(dict2bytes) + b'\x55\x55'
    return data_new


if __name__ == '__main__':
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    thread_rec = DeviceThread(sock, 'rec')
    thread_send = DeviceThread(sock, 'send')

    thread_rec.start()
    thread_send.start()

    thread_rec.join()
    thread_send.join()

    sock.close()
