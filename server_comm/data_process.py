# -*- coding: UTF-8 -*-
import requests
import datetime
import sqloperate, config
import logging
from decimal import Decimal
import json
import re


def start_service_inform():
    """
    服务器打开和关闭时，以报警信息通知微信
    inform_info = [data_dict['wellid'], d_id, ssid2sid[ss_id], s_name, desc[ss_id], station_info]
    :return:
    """
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inform_infos = [[0, 0, 0, '服务器打开和关闭', '服务器已打开', [0, 0, 0]]]
    notify_infos = [[0, '', 0, 0, '服务器', 0, '状态值', 0,
                     '服务器已打开', '服务器已打开', current_time]]
    inform_wechat(inform_infos, notify_infos)
    logging.debug("已通知微信：服务器已打开")


def stop_service_inform():
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inform_infos = [[0, 0, 0, '服务器打开和关闭', '服务器已关闭', [0, 0, 0]]]
    notify_infos = [[0, '', 0, 0, '服务器', 0, '状态值', 0,
                     '服务器已关闭', '服务器已关闭', current_time]]
    inform_wechat(inform_infos, notify_infos)
    logging.debug("已通知微信：服务器已关闭")


def process_online(data):
    """
    设备上线/在线：处理设备上报的数据
    主要分为两大类：1.设备第一次上线  2.设备非第一次上线
    :param data:
    :return:
    """
    data_dict = decode_binary_data(data)
    wellid = data_dict['wellid']

    isexist = sqloperate.device_get(wellid)
    if isexist is False:
        _device_firstonline(data_dict)
    else:
        _device_not_firstonline(data_dict)


def inform_on_off_line(wellid, type, state_old=None, state_new=None):
    """
    设备上线/离线通知
    两个操作：1.更改表device中的“设备运行状态status”字段   2.向微信发送上线/离线通知
    inform_infos = [[wellid, d_id, s_id, value, desc, station_info = [a,b,c]], ]
    :param data:
    :return:
    """

    if wellid is None:
        return

    try:
        station_info = get_stationinfo(wellid)
    except:
        station_info = [0, 0, 0]

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if type == 'online':
        logging.info("------------------Device {} 上线------------------".format(wellid))
        inform_infos = [[wellid, 0, 0, '设备上线和离线', '设备{}上线'.format(wellid), station_info]]
        notify_infos = [[0, '', 0, wellid, '设备{}'.format(wellid), 0, '状态值', 0,
                        '设备{}上线'.format(wellid), '设备{}上线'.format(wellid), current_time]]
    elif type == 'offline':
        logging.info("------------------Device {} 下线------------------".format(wellid))
        sqloperate.device_update_status(wellid, 0)  # 0表示下线
        inform_infos = [[wellid, 0, 0, '设备上线和离线', '设备{}下线'.format(wellid), station_info]]
        notify_infos = [[0, '', 0, wellid, '设备{}'.format(wellid), 0, '状态值', 0,
                        '设备{}下线'.format(wellid), '设备{}下线'.format(wellid), current_time]]
    elif type == 'status_switch':   # 部分内容固化了，后期可按需完善+++++++++++++++++++++++++++++++++++++++++++++++++++
        inform_infos = []    # 通知信息 inform_infos = [[wellid, d_id, s_id, value, desc, station_info = [a,b,c]], ]
        notify_infos = []    # 记录到notify表中的状态信息
        # notify_info_temp = [s_id, s_name, d_id, wellid, '设备{}'.format(wellid),
        #                     trigger_info[id], trigger_info[type], sensor_trigger[0],
        #                     trigger_info[desc], desc[ss_id], create_time]
        # trigger_info  {ss_id:[id, ss_id, s_name, alarm, current, type, c_x, c_y, c_m, desc, status, flag, freq, d_code], }
        # 启停机状态切换
        if state_new['wellstate'] != state_old['wellstate']:
            if state_new['wellstate'] == 0:    # 0表示停机
                inform_infos.append([wellid, 0, 0, '设备启停机', '设备{}停机'.format(wellid), station_info])
                notify_infos.append([0, '启停机', 0, wellid, '设备{}'.format(wellid), 0, '状态值', 0,
                                     '设备{}停机'.format(wellid), '设备{}停机'.format(wellid), current_time])
            else:                           # 1表示启机
                inform_infos.append([wellid, 0, 0, '设备启停机', '设备{}启机'.format(wellid), station_info])
                notify_infos.append([0, '启停机', 0, wellid, '设备{}'.format(wellid), 0, '状态值', 0,
                                     '设备{}启机'.format(wellid), '设备{}启机'.format(wellid), current_time])
        if state_new['acstate'] != state_old['acstate']:
            if state_new['acstate'] == 0:       # 0:交流没电
                inform_infos.append([wellid, 0, 0, '市电停来电', '设备{}交流电停电'.format(wellid), station_info])
                notify_infos.append([0, '市电停来电', 0, wellid, '设备{}'.format(wellid), 0, '状态值', 0,
                                     '设备{}交流电停电'.format(wellid), '设备{}交流电停电'.format(wellid), current_time])
            else:                           # 1表示来电
                inform_infos.append([wellid, 0, 0, '市电停来电', '设备{}交流电来电'.format(wellid), station_info])
                notify_infos.append([0, '市电停来电', 0, wellid, '设备{}'.format(wellid), 0, '状态值', 0,
                                     '设备{}交流电来电'.format(wellid), '设备{}交流电来电'.format(wellid), current_time])
    else:
        pass
    inform_wechat(inform_infos, notify_infos)


def _device_firstonline(data_dict):
    """
    设备第一次上线操作
    设备第一次上线，首先将设备的数据保存，然后向微信通知新设备上线
    设备第一次上线，不检测传感器是否异常，不报警。原因：设备的工厂等属性未配置，无法向指定用户发送报警信息，干脆就不检测了，后期有需要再完善
    数据保存包括：1.增加device表字段; 2.增加sensor表字段; 3.增加monitor表字段; 4.增加trigger表字段.
    :param data:
    :return:
    """
    wellid = data_dict['wellid']
    logging.info("设备（井号{}）为第一次上线...".format(wellid))
    create_time = data_dict['reporttime']
    # 平衡率 = 下冲程电流/上冲程电流
    balance_rate = get_balance_rate(data_dict['lowcurrent'], data_dict['upcurrent'], dict['wellstate'])

    # device表的操作：全部填写为固定的或者默认值
    sqloperate.device_add(data_dict)
    d_id = sqloperate.deviceid_of_wellid(wellid)  # 后续对数据库的所有操作均基于d_id

    # sensor表的操作：增加sensor字段时，value默认正常值和ex默认正常值0字段需要判断，其它字段都固定
    update_time = create_time
    sensor_01_sensor = (d_id, 1, '启停机', data_dict['wellstate'], 0, 0, '', '', create_time, update_time, 1, '')
    sensor_02_sensor = (d_id, 2, '市电停来电', data_dict['acstate'], 0, 0, '', '', create_time, update_time, 1, '')
    sensor_03_sensor = (d_id, 3, '电池状态', data_dict['batlow'], 0, 0, '', '', create_time, update_time, 1, '')
    sensor_04_sensor = (d_id, 4, '故障停状态', 0, 0, 0, '', '', create_time, update_time, 1, '')
    sensor_05_sensor = (d_id, 5, '皮带烧', data_dict['bell_exception'], 0, 0, '', '', create_time, update_time, 1, '')
    sensor_06_sensor = (d_id, 6, '曲柄销子', data_dict['crank_pin'], 0, 0, '', '', create_time, update_time, 1, '')
    sensor_07_sensor = (d_id, 7, '设备运行态', data_dict['model'], 0, 0, '', '', create_time, update_time, 1, '')
    sensor_08_sensor = (d_id, 8, '上冲程电流', data_dict['upcurrent'], 0, 0, '', '', create_time, update_time, 1, 'A')
    sensor_09_sensor = (d_id, 9, '下冲程电流', data_dict['lowcurrent'], 0, 0, '', '', create_time, update_time, 1, 'A')
    sensor_10_sensor = (d_id, 10, '运行电流', data_dict['nowcurrent'], 0, 0, '', '', create_time, update_time, 1, 'A')
    sensor_11_sensor = (d_id, 11, '平衡率', balance_rate, 0, 0, '', '', create_time, update_time, 1, '')
    sensor_12_sensor = (d_id, 12, '油压', data_dict['oil_pressure'], 0, 0, '', '', create_time, update_time, 1, 'MPA')
    sensor_13_sensor = (d_id, 13, '套压', data_dict['tao_pressure'], 0, 0, '', '', create_time, update_time, 1, 'MPA')
    sensor_14_sensor = (d_id, 14, '回压', data_dict['hui_pressure'], 0, 0, '', '', create_time, update_time, 1, 'MPA')
    sensor_list_sensor = [sensor_01_sensor, sensor_02_sensor, sensor_03_sensor, sensor_04_sensor,
                          sensor_05_sensor, sensor_06_sensor, sensor_07_sensor, sensor_08_sensor,
                          sensor_09_sensor, sensor_10_sensor, sensor_11_sensor, sensor_12_sensor,
                          sensor_13_sensor, sensor_14_sensor]
    sqloperate.sensor_add(sensor_list_sensor)

    # monitor表的操作：根据设备上报信息填写
    ssid2sid = sqloperate.sensor_get_ssid2sid(d_id)
    sensor_01_monitor = (d_id, ssid2sid[1], 1, '启停机', data_dict['wellstate'], create_time)
    sensor_02_monitor = (d_id, ssid2sid[2], 2, '市电停来电', data_dict['acstate'], create_time)
    sensor_03_monitor = (d_id, ssid2sid[3], 3, '电池状态', data_dict['batlow'], create_time)
    sensor_04_monitor = (d_id, ssid2sid[4], 4, '故障停状态', 0, create_time)
    sensor_05_monitor = (d_id, ssid2sid[5], 5, '皮带烧', data_dict['bell_exception'], create_time)
    sensor_06_monitor = (d_id, ssid2sid[6], 6, '曲柄销子', data_dict['crank_pin'], create_time)
    sensor_07_monitor = (d_id, ssid2sid[7], 7, '设备运行态', data_dict['model'], create_time)
    sensor_08_monitor = (d_id, ssid2sid[8], 8, '上冲程电流', data_dict['upcurrent'], create_time)
    sensor_09_monitor = (d_id, ssid2sid[9], 9, '下冲程电流', data_dict['lowcurrent'], create_time)
    sensor_10_monitor = (d_id, ssid2sid[10], 10, '运行电流', data_dict['nowcurrent'], create_time)
    sensor_11_monitor = (d_id, ssid2sid[11], 11, '平衡率', balance_rate, create_time)
    sensor_12_monitor = (d_id, ssid2sid[12], 12, '油压', data_dict['oil_pressure'], create_time)
    sensor_13_monitor = (d_id, ssid2sid[13], 13, '套压', data_dict['tao_pressure'], create_time)
    sensor_14_monitor = (d_id, ssid2sid[14], 14, '回压', data_dict['hui_pressure'], create_time)
    sensor_list_monitor = [sensor_01_monitor, sensor_02_monitor, sensor_03_monitor, sensor_04_monitor,
                           sensor_05_monitor, sensor_06_monitor, sensor_07_monitor, sensor_08_monitor,
                           sensor_09_monitor, sensor_10_monitor, sensor_11_monitor, sensor_12_monitor,
                           sensor_13_monitor, sensor_14_monitor]
    sqloperate.monitor_add(sensor_list_monitor)

    # trigger表的操作：全部填写为固定的或者默认值
    sqloperate.trigger_add(data_dict, d_id, ssid2sid)


def _device_not_firstonline(data_dict):
    """
    设备非第一次上线
    先保存设备数据，然后进行异常报警。保存数据前需要先检测相应的传感器是否处于激活状态
    :param data_dict:
    :return:
    """
    wellid = data_dict['wellid']
    logging.info("设备（井号{}）非第一次上线...".format(wellid))
    d_id = sqloperate.deviceid_of_wellid(wellid)  # 后续对数据库的所有操作均基于d_id

    flag_deleted = sqloperate.device_get_flag_deleted(wellid)
    if flag_deleted is True:    # 表示设备已标记为删除，则不进行后续各种处理
        return

    create_time = data_dict['reporttime']
    update_time = create_time
    balance_rate = get_balance_rate(data_dict['lowcurrent'], data_dict['upcurrent'], dict['wellstate'])

    # device表的操作：需要更新的字段有status, update_time, i_machine, h_machine
    sqloperate.device_update_status(wellid, 1)                # 1表示设备上线
    sqloperate.device_update_property_1(d_id, data_dict)    # 更新：update_time, i_machine, h_machine

    # monitor表的操作：添加设备数据，需要先判断传感器是否处于激活状态
    ssid2sid = sqloperate.sensor_get_ssid2sid(d_id)
    sensor_is_available = _sensor_is_available_detection(d_id)      # 0表示未激活，1表示激活
    sensor_01_monitor = (d_id, ssid2sid[1], 1, '启停机', data_dict['wellstate'], create_time)
    sensor_02_monitor = (d_id, ssid2sid[2], 2, '市电停来电', data_dict['acstate'], create_time)
    sensor_03_monitor = (d_id, ssid2sid[3], 3, '电池状态', data_dict['batlow'], create_time)
    sensor_04_monitor = (d_id, ssid2sid[4], 4, '故障停状态', 0, create_time)
    sensor_05_monitor = (d_id, ssid2sid[5], 5, '皮带烧', data_dict['bell_exception'], create_time)
    sensor_06_monitor = (d_id, ssid2sid[6], 6, '曲柄销子', data_dict['crank_pin'], create_time)
    sensor_07_monitor = (d_id, ssid2sid[7], 7, '设备运行态', data_dict['model'], create_time)
    sensor_08_monitor = (d_id, ssid2sid[8], 8, '上冲程电流', data_dict['upcurrent'], create_time)
    sensor_09_monitor = (d_id, ssid2sid[9], 9, '下冲程电流', data_dict['lowcurrent'], create_time)
    sensor_10_monitor = (d_id, ssid2sid[10], 10, '运行电流', data_dict['nowcurrent'], create_time)
    sensor_11_monitor = (d_id, ssid2sid[11], 11, '平衡率', balance_rate, create_time)
    sensor_12_monitor = (d_id, ssid2sid[12], 12, '油压', data_dict['oil_pressure'], create_time)
    sensor_13_monitor = (d_id, ssid2sid[13], 13, '套压', data_dict['tao_pressure'], create_time)
    sensor_14_monitor = (d_id, ssid2sid[14], 14, '回压', data_dict['hui_pressure'], create_time)
    sensor_list_monitor_before = [sensor_01_monitor, sensor_02_monitor, sensor_03_monitor, sensor_04_monitor,
                           sensor_05_monitor, sensor_06_monitor, sensor_07_monitor, sensor_08_monitor,
                           sensor_09_monitor, sensor_10_monitor, sensor_11_monitor, sensor_12_monitor,
                           sensor_13_monitor, sensor_14_monitor]

    sensor_list_monitor_after = []          # 保存被激活的传感器信息
    for key in sensor_is_available:
        if sensor_is_available[key] == 1:   # 1表示传感器处于激活状态
            sensor_list_monitor_after.append(sensor_list_monitor_before[key-1])
    sqloperate.monitor_add(sensor_list_monitor_after)

    # sensor表的操作：更新表数据，根据是否处于激活状态更新为不同的value和ex值

    # trigger_info  {ss_id:[id, ss_id, s_name, alarm, current, type, c_x, c_y, c_m, desc, status, flag, freq, d_code], }
    trigger_info = sqloperate.trigger_get(d_id)
    sensor_list_sensor, desc = _sensor_update_isactive(d_id, data_dict, sensor_is_available, trigger_info)
    sqloperate.sensor_update(d_id, sensor_list_sensor)

    # trigger表操作和异常报警操作：trigger表的操作暂时没写，也就是说一旦收到异常信息，不检测是否达到报警次数上限和报警频率，全都报警 +++++++++++++++++++++++++++++++++++++++++++
    alarm_required = []     # 报警信息 [[wellid, d_id, s_id, value, desc, station_info = [a,b,c]], ]
    notify_info = []        # 记录到notify表中的数据
    station_info = sqloperate.device_get_stationinfo(d_id)

    # sensor_trigger为 (value, ex, update_time, d_id, ss_id)
    for sensor_trigger in sensor_list_sensor:   # 触发异常的条件：1.设备未标记为删除（开始阶段已处理）  2.传感器有异常  3.传感器已启用
        if sensor_trigger[1] == 1:      # 2.传感器有异常
            ss_id = sensor_trigger[4]
            if sensor_is_available[ss_id] == 0:     # 3. 传感器未启用 sensor表：status字段
                continue

            s_name = trigger_info[ss_id][2]
            alarm_info = [data_dict['wellid'], d_id, ssid2sid[ss_id], s_name, desc[ss_id], station_info]
            alarm_required.append(alarm_info)

            notify_info_temp = [ssid2sid[ss_id], s_name, d_id, wellid, '设备{}'.format(wellid),
                                trigger_info[ss_id][0], trigger_info[ss_id][5], sensor_trigger[0],
                                trigger_info[ss_id][9], desc[ss_id], create_time]
            notify_info.append(notify_info_temp)

    # 向微信发送报警信息
    inform_wechat(alarm_required, notify_info)


def _sensor_is_available_detection(d_id):
    """
    检测设备d_id的所有传感器的激活状态
    :param d_id:
    :return:{ss_id:0/1, } 0表示未激活，1表示激活
    """
    sensor_is_available = {}    # {ss_id:0/1, } 0表示未激活，1表示激活
    sensor_info = sqloperate.sensor_get(d_id)
    for key in sensor_info:
        sensor_is_available[key] = sensor_info[key][4]  # 第4个值表示传感器的激活状态
    return sensor_is_available


def _sensor_update_isactive(d_id, data_dict, sensor_is_available, trigger_info):
    """
    sensor表的操作：更新表数据，根据是否处于激活状态更新为不同的value和ex值
    :param d_id:
    :param data_dict:
    :param sensor_is_available:
    :return:sensor_list_sensor, desc返回可作为sql参数的列表和对每个传感器的表述信息desc
    """
    update_time = data_dict['reporttime']
    balance_rate = get_balance_rate(data_dict['lowcurrent'], data_dict['upcurrent'], dict['wellstate'])

    # sensor (value, ex, update_time, d_id, ss_id)
    sensor_01_sensor = [0, 0, update_time, d_id, 1]
    sensor_02_sensor = [0, 0, update_time, d_id, 2]
    sensor_03_sensor = [0, 0, update_time, d_id, 3]
    sensor_04_sensor = [0, 0, update_time, d_id, 4]
    sensor_05_sensor = [0, 0, update_time, d_id, 5]
    sensor_06_sensor = [0, 0, update_time, d_id, 6]
    sensor_07_sensor = [0, 0, update_time, d_id, 7]
    sensor_08_sensor = [0, 0, update_time, d_id, 8]
    sensor_09_sensor = [0, 0, update_time, d_id, 9]
    sensor_10_sensor = [0, 0, update_time, d_id, 1]
    sensor_11_sensor = [0, 0, update_time, d_id, 11]
    sensor_12_sensor = [0, 0, update_time, d_id, 12]
    sensor_13_sensor = [0, 0, update_time, d_id, 13]
    sensor_14_sensor = [0, 0, update_time, d_id, 14]

    desc = {1: '正常', 2: '正常', 3: '正常', 4: '正常', 5: '正常', 6: '正常', 7: '正常',
            8: '正常', 9: '正常', 10: '正常', 11: '正常', 12: '正常', 13: '正常', 14: '正常'}

    if sensor_is_available[1] == 1:  # 启停机： 0表示关井，1表示开井
        sensor_01_sensor = [data_dict['wellstate'], 0, update_time, d_id, 1]  # 不报警

    ex_2 = 0
    if sensor_is_available[2] == 1:  # 市电停来电
        if data_dict['acstate'] == trigger_info[2][6]:
            # ex_2 = 1  # 0表示正常，1表示异常
            desc[2] = '市电停电'
        sensor_02_sensor = [data_dict['acstate'], ex_2, update_time, d_id, 2]

    ex_3 = 0
    if sensor_is_available[3] == 1:  # 电池状态
        if data_dict['batlow'] == trigger_info[3][6]:
            ex_3 = 1
            desc[3] = '电池电量低'
        sensor_03_sensor = [data_dict['batlow'], ex_3, update_time, d_id, 3]

    if sensor_is_available[4] == 1:  # 故障停状态
        pass  # 当①停电、②皮带烧、③曲棍哨子松动时，判断为故障停   在后续判断
        # sensor_04_sensor = (**, *ex *, update_time, d_id, 4)

    ex_5 = 0
    if sensor_is_available[5] == 1:  # 皮带烧
        if data_dict['bell_exception'] == trigger_info[5][6]:
            ex_5 = 1
            desc[5] = '皮带烧'
        sensor_05_sensor = [0, ex_5, update_time, d_id, 5]

    ex_6 = 0
    if sensor_is_available[6] == 1:  # 曲柄销子
        if data_dict['crank_pin'] == trigger_info[6][6]:
            ex_6 = 1
            desc[6] = '曲柄销子松动'
        sensor_06_sensor = [data_dict['crank_pin'], ex_6, update_time, d_id, 6]

    ex_7 = 0
    if sensor_is_available[7] == 1:  # 设备运行态：表示设备在线离线的触发条件
        # if data_dict['model'] == trigger_info[7][6]:
        #     ex_7 = 1
        #     desc[7] = '切换成了手动模式'
        sensor_07_sensor = [data_dict['model'], ex_7, update_time, d_id, 7]  # 不报警

    ex_8 = 0    # 上下冲程电流无论多大多小都不报警，只在平衡率异常时才报警，因此ex_8 = 0,不会为1。
    if sensor_is_available[8] == 1:  # 上冲程电流
        if data_dict['upcurrent'] < trigger_info[8][6]:
            # ex_8 = 1
            desc[8] = '上冲程电流为{}A，小于正常范围({}A~{}A).'.format(data_dict['upcurrent'], trigger_info[8][6], trigger_info[8][7])
        elif data_dict['upcurrent'] > trigger_info[8][7]:
            # ex_8 = 1
            desc[8] = '上冲程电流为{}A，大于正常范围({}A~{}A).'.format(data_dict['upcurrent'], trigger_info[8][6], trigger_info[8][7])
        sensor_08_sensor = [data_dict['upcurrent'], ex_8, update_time, d_id, 8]

    ex_9 = 0
    if sensor_is_available[9] == 1:  # 下冲程电流
        if data_dict['lowcurrent'] < trigger_info[9][6]:
            # ex_9 = 1
            desc[9] = '下冲程电流为{}A，小于正常范围({}A~{}A).'.format(data_dict['lowcurrent'], trigger_info[9][6], trigger_info[9][7])
        elif data_dict['lowcurrent'] > trigger_info[9][7]:
            # ex_9 = 1
            desc[9] = '下冲程电流为{}A，大于正常范围({}A~{}A).'.format(data_dict['lowcurrent'], trigger_info[9][6], trigger_info[9][7])
        sensor_09_sensor = [data_dict['lowcurrent'], ex_9, update_time, d_id, 9]

    ex_10 = 0
    if sensor_is_available[10] == 1:  # 运行电流
        sensor_10_sensor = [data_dict['nowcurrent'], ex_10, update_time, d_id, 10]  # 不报警

    ex_11 = 0
    if sensor_is_available[11] == 1:  # 平衡率
        if balance_rate < trigger_info[11][6]:
            ex_11 = 1
            desc[11] = '平衡率为{}%。上冲程电流为{}A，下冲程电流为{}A，当前电流为{}A。'.format(
                balance_rate, data_dict['upcurrent'], data_dict['lowcurrent'], data_dict['nowcurrent'])
        elif balance_rate > trigger_info[11][7]:
            ex_11 = 1
            desc[11] = '平衡率为{}%。上冲程电流为{}A，下冲程电流为{}A，当前电流为{}A。'.format(
                balance_rate, data_dict['upcurrent'], data_dict['lowcurrent'], data_dict['nowcurrent'])
        sensor_11_sensor = [balance_rate, ex_11, update_time, d_id, 11]

    ex_12 = 0
    if sensor_is_available[12] == 1:  # 油压
        if data_dict['oil_pressure'] < trigger_info[12][6]:
            ex_12 = 1
            desc[12] = '油压为{}，低于正常范围({}~{}).'.format(data_dict['oil_pressure'], trigger_info[12][6], trigger_info[12][7])
        elif data_dict['oil_pressure'] > trigger_info[12][7]:
            ex_12 = 1
            desc[12] = '油压为{}，高于正常范围({}~{}).'.format(data_dict['oil_pressure'], trigger_info[12][6], trigger_info[12][7])
        sensor_12_sensor = [data_dict['oil_pressure'], ex_12, update_time, d_id, 12]

    ex_13 = 0
    if sensor_is_available[13] == 1:  # 套压
        if data_dict['tao_pressure'] < trigger_info[13][6]:
            ex_13 = 1
            desc[13] = '套压为{}，低于正常范围({}~{}).'.format(data_dict['tao_pressure'], trigger_info[13][6], trigger_info[13][7])
        elif data_dict['tao_pressure'] > trigger_info[13][7]:
            ex_13 = 1
            desc[13] = '套压为{}，高于正常范围({}~{}).'.format(data_dict['tao_pressure'], trigger_info[13][6], trigger_info[13][7])
        sensor_13_sensor = [data_dict['tao_pressure'], ex_13, update_time, d_id, 13]

    ex_14 = 0
    if sensor_is_available[14] == 1:  # 回压
        if data_dict['hui_pressure'] < trigger_info[14][6]:
            ex_14 = 1
            desc[14] = '回压为{}，低于正常范围({}~{}).'.format(data_dict['hui_pressure'], trigger_info[14][6], trigger_info[14][7])
        elif data_dict['hui_pressure'] > trigger_info[14][7]:
            ex_14 = 1
            desc[14] = '回压为{}，高于正常范围({}~{}).'.format(data_dict['hui_pressure'], trigger_info[14][6], trigger_info[14][7])
        sensor_14_sensor = [data_dict['hui_pressure'], ex_14, update_time, d_id, 14]

    if sensor_is_available[4] == 1:  # 故障停状态,当①停电、②皮带烧ex_5、③曲柄销子松动ex_6时，判断为故障停  ++++++++++++++++++++++++++++++++++++++++++++++++++++++
        if ex_5 == 1 or ex_6 == 1:
            value_4 = 1
            ex_4 = 1
            desc[4] = '故障停机，原因：'
            if ex_5 == 1:
                desc[4] = desc[4] + '皮带烧 '
            if ex_6 == 1:
                desc[4] = desc[4] + '曲柄销子松动 '
        else:
            value_4 = 0
            ex_4 = 0
        sensor_04_sensor = [value_4, ex_4, update_time, d_id, 4]

    sensor_list_sensor = [sensor_01_sensor, sensor_02_sensor, sensor_03_sensor, sensor_04_sensor,
                          sensor_05_sensor, sensor_06_sensor, sensor_07_sensor, sensor_08_sensor,
                          sensor_09_sensor, sensor_10_sensor, sensor_11_sensor, sensor_12_sensor,
                          sensor_13_sensor, sensor_14_sensor]
    return sensor_list_sensor, desc


def get_stationinfo(wellid):
    d_id = sqloperate.deviceid_of_wellid(wellid)
    if d_id is None:
        stationinfo = [0, 0, 0]
    else:
        stationinfo = sqloperate.device_get_stationinfo(d_id)
    return stationinfo


def check_data(data):
    """
    校验收到的数据是否符合协议要求
    使用正则表达式校验收到的字符，收到的字符会出现以下几种情况：
    1. 收到的数据开始和结束标志不符合协议要求
    2. 重复收到多份符合协议字段的数据
    3. 收到的数据长度不符合协议要求
    :param data:
    :return:True/False, data_cut
    """
    # 1.1 判断数据开始字段是否符合协议要求
    if data[0:2] == b'\xaa\xaa':        # 设备上报数据的格式
        data_len = config.data_len
    elif data[0:2] == b'\xbb\xbb':      # 控制命令的格式
        data_len = config.control_len
    else:
        logging.info("开始标志不符合协议要求，收到的数据为：{}".format(data))
        return False, None

    # 1.2 判断数据结束字段是否符合协议要求
    flag_end = re.search(b'\x55\x55', data)
    if flag_end is None:
        logging.info("结束标志不符合协议要求，收到的数据为：{}".format(data))
        return False, None

    # 2. 截取第一个开始标志和结束标志中间的数据
    data_cut = re.split(b'\x55\x55', data)[0] + b'\x55\x55'

    # 3. 判断数据长度是否符合协议要求
    if len(data_cut) % data_len != 0:
        logging.info("数据长度为{}, 不符合协议要求".format(len(data_cut)))
        return False, None

    # 数据符合协议要求
    # logging.debug("数据校验成功")
    return True, data_cut


def decode_binary_data(data):
    """
    将接收到的十六进制转换为dict类型，dict中存储的为int 和 float 类型数据
    :param data: 十六进制比特流数据
    :return:返回dict类型的原始数据
    """
    if check_data(data) is False:
        return None

    wellid = data[2] + data[3] * 2 ** 8 + data[4] * 2 ** 16 + data[5] * 2 ** 32
    dict = {}
    dict['wellid'] = wellid         # 油井编号
    dict['reporttime'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dict['acstate'] = data[8]       # 交流是否有电
    dict['batlow'] = data[9]        # 电池是否电量低
    dict['wellstate'] = data[10]    # 开/关井状态
    dict['model'] = data[11]        # 自动/手动模式
    dict['manual_switch_state'] = data[12]              # 手动开关状态
    # dict['nowcurrent'] = data[13] + 0.1 * data[14]      # 当前电流信息
    # dict['upcurrent'] = data[15] + 0.1 * data[16]       # 上死点电流信息
    # dict['lowcurrent'] = data[17] + 0.1 * data[18]      # 下死点电流信息

    # 修改：实际电流 = （5.09 * 采集到的电流 * 100) / (1024 * 3.3)   注：上报的电流数据为16B, 取后10位
    nowcurrent = 5.09 * ((data[13] & 3) * 256 + data[14]) * 100 / (1024 * 3.3)
    upcurrent = 5.09 * ((data[15] & 3) * 256 + data[16]) * 100 / (1024 * 3.3)
    lowcurrent = 5.09 * ((data[17] & 3) * 256 + data[18]) * 100 / (1024 * 3.3)

    dict['nowcurrent'] = Decimal(nowcurrent).quantize(Decimal('0.00'))      # 当前电流信息
    dict['upcurrent'] = Decimal(upcurrent).quantize(Decimal('0.00'))   # 上死点电流信息
    dict['lowcurrent'] = Decimal(lowcurrent).quantize(Decimal('0.00'))      # 下死点电流信息

    logging.debug("收集到的电流  当前电流：{}, 上冲程电流：{}, 下冲程电流：{}"
                  .format((data[13] & 3) * 256 + data[14], (data[15] & 3) * 256 + data[16], (data[17] & 3) * 256 + data[18]))
    logging.debug("转换后的电流  当前电流：{}, 上冲程电流：{}, 下冲程电流：{}"
                  .format(dict['nowcurrent'], dict['upcurrent'], dict['lowcurrent']))

    dict['bell_exception'] = data[19]                   # 皮带烧
    dict['crank_pin'] = data[20]                        # 曲柄销子 一种类似于螺丝的零件
    dict['oil_pressure'] = data[21] + 0.1 * data[22]    # 油压
    dict['tao_pressure'] = data[23] + 0.1 * data[24]    # 套压
    dict['hui_pressure'] = data[25] + 0.1 * data[26]    # 回压

    # 若井处于关闭状态，则上报的电流数据为随机值，此时在服务器端将此随机值更改为0.
    if dict['wellstate'] == 0:
        dict['nowcurrent'] = 0  # 当前电流信息
        dict['upcurrent'] = 0   # 上死点电流信息
        dict['lowcurrent'] = 0  # 下死点电流信息
    return dict


def decode_wechat_data(data):
    """
    解析微信控制命令帧
    :param data:
    :return:返回截取后的data2device和dict类型的原始数据
    """
    if check_data(data) is False:
        return None, None

    data2device = data[6:]  # 截取微信控制命令帧，将截取后的转发给device

    # data = b'\xbb\xbb\x58\x02\x00\x00\xaa\xaa\x00\x02\x00\x08\x02\x08\x01\x08\x00\x55\x55'
    # data2device =                  b'\xaa\xaa\x00\x02\x00\x08\x02\x08\x01\x08\x00\x55\x55'

    dict = {}
    dict['wellid'] = data[2] + data[3] * 2 ** 8 + data[4] * 2 ** 16 + data[5] * 2 ** 32
    dict['function_code'] = data[8]
    dict['time_interval_timer'] = (data[9], data[10])      # (hour, min) 第一个字节单位：时；第二个字节单位：分钟
    dict['open_time'] = (data[11], data[12])
    dict['close_time'] = (data[13], data[14])
    dict['current_time'] = (data[15], data[16])

    return data2device, dict


def show_wechat_command(data_dict):
    """
    收到微信的控制命令后，模拟更新设备状态device_data
    :param data_control:
    :return:
    """
    # data_dict = {}      # 记录典型微信控制命令
    # data_dict['function_code'] = data[2]
    # data_dict['time_interval_timer'] = (data[3], data[4])  # (hour, min) 第一个字节单位：时；第二个字节单位：分钟
    # data_dict['open_time'] = (data[5], data[6])
    # data_dict['close_time'] = (data[7], data[8])
    # data_dict['current_time'] = (data[9], data[10])

    function_code = data_dict['function_code']
    logging.info("收到的控制命令为：")
    if function_code == 0 or function_code == 1:    # 开关井定时打开/关闭
        start = "{}:{}".format(data_dict['open_time'][0], data_dict['open_time'][1])
        end = "{}:{}".format(data_dict['close_time'][0], data_dict['close_time'][1])
        if function_code == 0:
            logging.info("======================================")
            logging.info("== 打开定时开关井   定时：{} - {}".format(start, end))
            logging.info("======================================")
        if function_code == 1:
            logging.info("======================================")
            logging.info("== 关闭定时开关井   定时：{} - {}".format(start, end))
            logging.info("======================================")

    if function_code == 2 or function_code == 3:    # 间隔上报打开/关闭
        interval = "{}:{}".format(data_dict['time_interval_timer'][0], data_dict['time_interval_timer'][1])
        if function_code == 2:
            logging.info("======================================")
            logging.info("== 打开间隔上报     间隔：{}".format(interval))
            logging.info("======================================")
        if function_code == 3:
            logging.info("======================================")
            logging.info("== 关闭间隔上报     间隔：{}".format(interval))
            logging.info("======================================")

    if function_code == 4 or function_code == 5:    # 立即开井/关井
        if function_code == 4:
            logging.info("======================================")
            logging.info("==            立即开井                =")
            logging.info("======================================")
        if function_code == 5:
            logging.info("======================================")
            logging.info("==            立即关井                =")
            logging.info("======================================")

    if function_code == 6:      # 设定时间
        current_time = "{}:{}".format(data_dict['current_time'][0], data_dict['current_time'][1])
        logging.info("======================================")
        logging.info("==  设定时间    设置为：{}".format(current_time))
        logging.info("======================================")


def get_balance_rate(lowcurrent, upcurrent, wellstate):
    """
    # 平衡率 = 下冲程电流/上冲程电流
    :param lowcurrent:
    :param upcurrent:
    :return:
    """
    balance_rate = 0
    if upcurrent != 0:
        balance_rate = (lowcurrent / upcurrent) * 100
    if wellstate == 0:
        balance_rate = 100
    res = Decimal(balance_rate).quantize(Decimal('0.00'))
    return res


def support_version_1(data):
    """
    兼容第一代帧格式
    :param data:
    :return:
    """
    logging.info("【收到的数据为第一版帧格式】")

    # 1. 判断数据开始/结束字段是否符合协议要求
    flag_end = re.search(b'\x55\x55', data)
    if data[0:2] != b'\xaa\xaa' or flag_end is None:
        logging.info("[v1.0]结束标志不符合协议要求，收到的数据为：{}".format(data))
        return data

    # 2. 截取第一个开始标志和结束标志中间的数据
    data_cut = re.split(b'\x55\x55', data)[0] + b'\x55\x55'

    if len(data_cut) != 19:
        return data

    data_v1 = data_cut
    data_v2 = data_v1[0:2] + data_v1[2:3] + b'\x00\x00\x00' + data_v1[3:5] + data_v1[5:6] + data_v1[6:7] + \
              data_v1[7:8] + data_v1[8:9] + data_v1[9:10] + data_v1[10:12] + data_v1[12:14] + data_v1[14:16] + \
              data_v1[16:17] + b'\x00' + b'\x00\x05' + b'\x00\x00' + b'\x00\x05' + b'\x55\x55'
    # print("data_v1 = {}".format(data_v1))
    # print("data_v2 = {}".format(data_v2))
    logging.debug("已转换为第二版帧格式")
    return data_v2


def inform_wechat(alarm_info, notify_info):
    """
    向微信发送通知
    :param alarm_info: list数据，[[wellid, d_id, s_id, value, desc, station_info = [a,b,c]], ]
    :param notify_info: 记录到数据库表notify中的信息
    :return:
    """
    if len(alarm_info) == 0:  # 表示无报警信息
        # logging.debug("无报警信息")
        return

    dict2wechat = {}
    dict2wechat['data'] = json.dumps(alarm_info)

    # post请求   get请求为：response = requests.get(url, params=dict2wechat)
    url = 'https://wwstudio.vip/wx/api/v1/sendTemplate'
    response = requests.post(url, data=dict2wechat)
    # logging.debug("报警通知返回信息：{}".format(response.text))

    logging.info("已向微信发送报警信息：")
    logging.info(alarm_info)
    # logging.info(dict2wechat)

    # 报警信息记录到表notify
    sqloperate.notify_add(notify_info)
