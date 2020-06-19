# -*- coding: UTF-8 -*-
import threading
import time
import socket
import logging
import json
import decimal

import sqloperate, config, data_process

# 全局变量
wechat_conns = []           # [[conn, addr, wellid], ] 保存微信的连接, addr和其控制的井id的对应关系
device_conns = []           # [[conn, addr, wellid], ] 保存设备的连接, addr和其id的对应关系

threads = []                # 保存当前所有线程
mutex = threading.Lock()    # 确保数据的互斥访问


class ServerThread(threading.Thread):
    def __init__(self, conn, addr, conn_type):
        threading.Thread.__init__(self)
        self.conn = conn
        self.addr = addr
        self.conn_type = conn_type

    def run(self):
        logging.debug("---------------------------------------------")
        if self.conn_type == "device":
            logging.debug("------------------设备网络接入------------------")
            logging.debug("新线程开启服务于 设备({}：{})".format(self.addr[0], self.addr[1]))
            _conn_process_device(self.conn, self.addr)
        elif self.conn_type == "wechat":
            logging.debug("------------------微信接入------------------")
            logging.debug("新线程开启服务于 微信({}：{})".format(self.addr[0], self.addr[1]))
            _conn_process_wechat(self.conn, self.addr)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        super(DecimalEncoder, self).default(o)


def _conn_process_device(conn, addr):
    """
    处理来自设备device的socket连接
    :param conn:
    :param addr:
    :return:
    """
    wellid = None
    firstonlineflag = True
    need_settime = True
    latest_status = {}      # 记录设备当前的状态，包含所有上报的状态

    while True:
        # 1.接收数据
        logging.info("---")
        logging.info("正在准备接收-Device {}-的数据...".format(wellid))
        try:
            data = conn.recv(1024)
        except Exception as ex:
            # 设备连接异常断开，向微信发送提醒
            _del_device_conn(conn)
            logging.debug("接收状态异常，设备下线")
            data_process.inform_on_off_line(wellid, type='offline')
            break
        logging.info("收到device信息：{}".format(data))

        # 设备第一次上线的操作：发送对时命令
        # 每个连接线程收到的第一个数据包都不会被处理，仅仅会触发服务器下发对时命令，对时命令下发后收到的报文视为第一个有用报文
        if firstonlineflag is True and need_settime is True:
            time.sleep(4)       # 设备网络接入后，等待4秒后设备稳定了再发对时命令
            nowtime = time.localtime()
            send_data = b'\xaa\xaa\x06\x00\x00\x00\x00\x00\x00' + \
                        bytes([nowtime.tm_hour, nowtime.tm_min]) + b'\x55\x55'
            conn.send(send_data)
            logging.info("已向新Device发送对时命令：{}".format(send_data))
            need_settime = False
            continue

        # 2.处理数据
        if len(data) == 0:
            # 客户端的socket连接关闭的时候，服务器端就会收到大量的空包
            # 设备连接异常断开，向微信发送提醒
            _del_device_conn(conn)
            logging.debug("收到空包,表示设备断开. data = {}".format(data))
            data_process.inform_on_off_line(wellid, type='offline')
            break

        if len(data) < 3:
            logging.debug("收到的信息无效: len(data) < 3")
            continue

        if data[0:2] == b'\xcc\xcc':        # 心跳包
            # logging.info("收到的是Device心跳包信息：{}".format(data))

            continue
        elif data[0:2] == b'\xaa\xaa':  # 传感器上报的状态信息
            # 兼容第一版帧格式
            data = data_process.support_version_1(data)

            if data_process.check_data(data) is False:
                continue

            '''
            处理流程：1.接收数据，2.反馈给wechat，3.处理数据：包括保存数据,异常检测,报警处理
            后期优化：使用多线程处理
            '''
            # ========================================
            # 1.接收数据
            data_dict = data_process.decode_binary_data(data)
            wellid = data_dict['wellid']

            """
            判断设备是否为第一次上线
            之所以加上这个判断，是因为设备可能使用的新的TCP连接，旧连接并没有释放
            """
            if _get_device_conn(wellid) is not None:        # 存在该设备对应的连接
                if _get_device_conn(wellid) is not conn:    # 该连接不是此连接
                    logging.debug("设备{}使用了一个新的TCP连接，而不是已存在的旧的TCP连接".format(wellid))
                    _del_device_conn_with_wellid(wellid)
                    _store_device_conn(conn, addr, wellid)
                    firstonlineflag = False

            # 设备第一次上线的操作
            if firstonlineflag is True:
                # _del_device_conn_with_wellid(wellid)
                _store_device_conn(conn, addr, wellid)
                data_process.inform_on_off_line(wellid, type='online')
                firstonlineflag = False

            # 状态切换提醒
            if len(latest_status) != 0:
                data_process.inform_on_off_line(wellid, type='status_switch', state_old=latest_status, state_new=data_dict)
            latest_status = data_dict

            # ========================================
            # 2.反馈给wechat
            try:
                # logging.debug("判断是否需要反馈给wechat...")
                wechat_conn = _get_wechat_conn(wellid)
                if wechat_conn is not None:
                    # 1.需要反馈
                    logging.info("此次上报的-Device {}- 的数据需要反馈给wechat".format(wellid))

                    # 2.使用json格式封装
                    dict_res = {}
                    dict_res["result"] = 0  # 成功
                    dict_res["data"] = data_dict

                    # 3.使用wxapp的连接conn发送数据
                    wechat_conn.send(bytes(json.dumps(dict_res, cls=DecimalEncoder), encoding='utf8'))
                    logging.info("已反馈给wxapp Device {} 的数据".format(wellid))

                    # 4.发送反馈后执行后续处理，包括：将临时保存的连接，并且删掉微信对应的conn
                    _del_wechat_conn(wechat_conn)
            except Exception as ex:
                logging.info("接收到的数据反馈给微信时发生异常，信息如下：{}".format(ex))
                _del_wechat_conn(wechat_conn)
                continue

            # ========================================
            # 3.处理数据：包括保存数据,数据异常检测和报警
            data_process.process_online(data)

        else:
            logging.debug("收到的信息无效")
            continue


def _conn_process_wechat(conn, addr):
    """
    处理来自设备wechat的socket连接
    :param conn:
    :param addr:
    :return:
    """
    # while True:
    # 1.接收数据
    logging.info("---")
    logging.info("正在准备接收-wechat-的数据...")
    try:
        data = conn.recv(1024)
    except Exception as ex:
        # logging.info("连接断开,详情：ConnectionResetError: [WinError 10054] 远程主机强迫关闭了一个现有的连接。")
        logging.info("连接断开，详情：{}".format(ex))
        _del_wechat_conn(conn)
        # break
        return

    logging.info("收到-wechat-的数据为：{}".format(data))
    # 2.处理数据
    if len(data) == 0:
        # 关闭与微信的连接后，会收到来自微信的一个空数据
        # 收到这个空数据后就与微信断开了连接
        logging.debug("收到来自wechat的空数据：{}".format(data))
        _del_wechat_conn(conn)
        # break
        return

    check_result, data = data_process.check_data(data)
    if check_result is False:
        dict_res = {"result": -8, "data": None, "info": "收到无效信息"}
        conn.send(bytes(json.dumps(dict_res, cls=DecimalEncoder), encoding='utf8'))
        _del_wechat_conn(conn)
        # break
        return

    if data[0:2] == b'\xbb\xbb':  # 是用户发出的控制命令
        # logging.info("收到-wechat-的数据为：{}".format(data))
        # =============================================================================
        # 1.转发用户控制命令
        # 1.1.提取被控设备的wellid,并记录井这次上报的信息需要反馈给wechat
        data2device, data_dict = data_process.decode_wechat_data(data)
        data_process.show_wechat_command(data_dict)     # 显示控制命令
        wellid_controled = data_dict['wellid']
        # 检查设备是否在控制中，保证同一时刻只允许一个用户的控制
        wechat_conn = _get_wechat_conn(wellid_controled)
        if wechat_conn is not None:     # 设备正在被控制中
            logging.info("当前Device {} 正在被控制中!".format(wellid_controled))
            dict_res = {"result": -8, "data": None, "info": "当前设备正在被控制中"}
            conn.send(bytes(json.dumps(dict_res, cls=DecimalEncoder), encoding='utf8'))
            _del_wechat_conn(conn)
            # break
            return

        _store_wechat_conn(conn, addr, wellid_controled)        # ------保存conn-------

        # 1.2.使用被控对象的的conn发送控制命令
        logging.debug("使用Device的conn转发控制码...")
        device_conn = _get_device_conn(wellid_controled)
        logging.debug("device_conn = {}".format(device_conn))
        if device_conn is None:
            # 返回用户不在线信息
            dict = {}
            dict['device_status'] = 0
            dict['desc'] = 'The current well is offline.'
            dict_res = {}
            dict_res["result"] = -8  # 失败
            dict_res["data"] = dict
            conn.send(bytes(json.dumps(dict_res, cls=DecimalEncoder), encoding='utf8'))
            logging.error("!!!找不到-Device{}-的conn,已向用户反馈：{}!!!".format(wellid_controled, dict_res))
            # continue
            return

        # 完善：向设备发送控制码后，设备可能没有正确接收控制码，导致设备无反馈信息
        # 在此，通过重传机制提高可靠性
        exit_flag = True
        try_times = 0
        while exit_flag and try_times != 3:
            try_times = try_times + 1
            device_conn.send(data2device)
            logging.info("+++第{}次向-Device {} -发送控制码{}".format(try_times, wellid_controled, data2device))

            time.sleep(2)
            if _get_wechat_conn(wellid_controled) is None:
                exit_flag = True
            else:
                exit_flag = False
        if try_times == 3:
            logging.error("无法控制设备：已尝试向设备{}发送{}次控制码，仍无法接收到设备的反馈消息！".format(wellid_controled, try_times))
            logging.info("已将该错误返回给微信。")
            dict_res = {"result": -8, "data": None, "info": "无法控制该设备"}
            conn.send(bytes(json.dumps(dict_res, cls=DecimalEncoder), encoding='utf8'))
            _del_wechat_conn(conn)

        # =============================================================================
        # 2.给用户返回信息
        # 被控的传感器收到数据后，使用该wxapp的conn将数据返回
        # 相关处理包含在device_conn中的是否需要反馈模块中

        # =============================================================================
        # 3.更新数据库表device字段,包括：上报间隔、定时开关井、手自动指示
        sqloperate.device_update_property_2(data_dict)

    else:
        logging.debug("收到无效信息：{}".format(data))
        # continue
        return
    return


# ==================================
# 设置全局变量,包含三个操作：保存,获取,删除
# 设置微信连接操作
def _store_wechat_conn(conn, addr, wellid='-1'):
    """ 1.保存
    保存微信的socket连接
    :param conn:
    :param addr:
    :param wellid:'-1'表示井号未知,收到wechat的控制命令时能够获取到wellid,并及时更新该wellid
    :return:
    """
    if wellid != '-1':
        mutex.acquire()
        for conn_1 in wechat_conns:
            if conn_1[0] is conn:
                logging.debug("_store_wechat_conn():conn已存在，只需更新wellid")
                conn_1[2] = wellid
                mutex.release()
                logging.debug("++++++++++++++++++++++++++++++++++++")
                logging.debug("当前所有连接 wechat_conns = {}".format(wechat_conns))
                logging.debug("++++++++++++++++++++++++++++++++++++")
                return
        mutex.release()
        logging.debug("_store_wechat_conn()：不存在未知wellid的conn。 这行命令应该不会出现。")

    conn_temp = [conn, addr, wellid]
    mutex.acquire()
    wechat_conns.append(conn_temp)
    mutex.release()


def _get_wechat_conn(wellid):
    """ 2.获取
    根据所控制的wellid找到相应的wechat连接conn:当控制命令发送完成后，需要使用wechat的conn连接将结果反馈给微信
    :param wellid:
    :return:若存在，返回wechat的conn；否则，返回None
    """
    mutex.acquire()
    for conn_temp in wechat_conns:
        if conn_temp[2] == wellid:
            conn = conn_temp[0]
            mutex.release()
            return conn
    mutex.release()
    return None


def _del_wechat_conn(conn):
    """ 3.删除
    根据所连接的conn删除相应的微信连接
    :param wellid:
    :return:
    """
    logging.debug("准备删除wechat的conn...")
    mutex.acquire()
    for conn_temp in wechat_conns:
        if conn_temp[0] is conn:        # ？？？is正确吗+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            # 1.关闭socket连接
            conn_temp[0].close()
            try:
                conn.close()
                logging.debug("wechat的conn关闭成功。")
            except Exception:
                logging.info("conn连接关闭异常，信息如下：", Exception)

            # 2.删除保存的连接
            wechat_conns.remove(conn_temp)
            mutex.release()
            return
    mutex.release()
    logging.debug("_del_wechat_conn():无此连接conn，无法完成删除")
    return


# 设置设备连接操作
def _store_device_conn(conn, addr, wellid='-1'):
    """ 1.保存
    保存设备的socket连接
    :param conn:
    :param addr:
    :param wellid:'-1'表示井号未知,收到设备上报信息时能够获取到wellid,并及时更新该wellid
    :return:
    """
    if wellid != '-1':
        mutex.acquire()
        for conn_1 in device_conns:
            if conn_1[0] is conn:
                logging.debug("_store_device_conn():conn已存在，只需更新wellid为{}".format(wellid))
                conn_1[2] = wellid
                mutex.release()
                logging.debug("++++++++++++++++++++++++++++++++++++")
                logging.debug("当前所有连接 devices_conns = {}".format(device_conns))
                logging.debug("++++++++++++++++++++++++++++++++++++")
                return
        mutex.release()
        logging.debug("_store_device_conn()：不存在未知wellid的conn。 这行命令应该不会出现。")

    conn_temp = [conn, addr, wellid]
    mutex.acquire()
    device_conns.append(conn_temp)
    mutex.release()


def _get_device_conn(wellid):
    """ 2.获取
    根据设备的wellid获取其连接conn
    :param wellid:
    :return:若存在，返回device的conn；否则，返回None
    """
    mutex.acquire()
    for conn_temp in device_conns:
        if conn_temp[2] == wellid:
            conn = conn_temp[0]
            mutex.release()
            return conn
    mutex.release()
    return None


def _del_device_conn(conn):
    """ 3.删除
    根据所连接的conn删除相应的设备连接
    :param wellid:
    :return:
    """
    logging.debug("准备删除设备的conn...")
    mutex.acquire()
    for conn_temp in device_conns:
        if conn_temp[0] is conn:        # ？？？is正确吗
            # 1.关闭socket连接
            try:
                conn.close()
                logging.info("已关闭device的conn连接")
            except Exception:
                logging.info("conn连接关闭异常，信息如下：", Exception)

            # 2.删除保存的连接
            device_conns.remove(conn_temp)
            # mutex.release()
            # return
    mutex.release()
    # logging.debug("_del_device_conn():无此连接conn，无法完成删除")
    return


def _del_device_conn_with_wellid(wellid):
    """
    由于每次上报的数据都使用的是新的TCP连接，并且旧连接并不会被正常关闭，导致device_conns中保存了大量的旧连接，需要将其删除
    :param wellid:
    :return:
    """
    logging.debug("准备删除该设备的未正常释放的conn连接...")
    mutex.acquire()
    for conn_temp in device_conns:
        if conn_temp[2] == wellid:
            # 1.关闭socket连接
            try:
                conn_temp[0].close()
                logging.info("（旧连接）已关闭device的conn旧连接")
            except Exception:
                logging.info("conn连接关闭异常，信息如下：", Exception)

            # 2.删除保存的连接
            device_conns.remove(conn_temp)
            # mutex.release()
            # return
    mutex.release()
    # logging.debug("_del_device_conn():无此连接conn，无法完成删除")
    return


# 主进程，可供其它模块函数调用
def server_thread():
    """ 主进程
    用户在进程中开启多线程
    :return:
    """

    sqloperate.update_wellid_to_deviceid()

    # socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((config.server_ip, config.server_port))
    sock.listen()

    # 服务器打开和关闭时，以报警信息通知微信
    data_process.start_service_inform()

    # 控制信道使用多线程同时接收多个用户的连接
    while True:
        logging.info("正在监听{}：{}...".format(config.server_ip, config.server_port))
        conn, addr = sock.accept()  # addr =  ('127.0.0.1', 49382)

        # 判断该连接类型：微信连接 or 设备连接
        conn_type = None
        if addr[0] == '127.0.0.1':
            conn_type = "wechat"
            _store_wechat_conn(conn, addr)
        else:
            conn_type = "device"
            _store_device_conn(conn, addr)

        thread = ServerThread(conn, addr, conn_type)
        thread.start()
        # threads.append(thread)

    # sock.close()
    # logging.info("退出主线程...")


if __name__ == "__main__":
    server_thread()
