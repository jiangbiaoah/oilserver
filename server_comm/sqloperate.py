# -*- coding: UTF-8 -*-
import pymysql
import datetime
import config
import logging


host = config.sql_host
username = config.sql_username
password = config.sql_password

# database_name = "oilapp"
database_name = config.database_name

wellid_deviceid = {}    # {code:d_id,} 设备号和设备id的对应关系，即device表中code与id的对应,在socket服务启动前和新增设备后更新此对应关系


# =========================================
# 表device的操作：1.增加  2.更新  3.查询
# 1.增加
def device_add(data_dict):
    msg_device = {}     # 共18个字段
    msg_device['code'] = data_dict['wellid']    # 设备编码wellid
    msg_device['name'] = '设备{}'.format(data_dict['wellid'])         # 设备名称
    msg_device['factory'] = 0       # 用户所属矿厂默认为0
    msg_device['team'] = 0          # 用户所属作业区
    msg_device['station'] = 0       # 用户所属小组
    msg_device['status'] = 1        # 设备运行状态. 1表示上线, 0表示下线
    msg_device['geo_x'] = ''        # 经度
    msg_device['geo_y'] = ''        # 纬度
    msg_device['flag'] = 0          # 标记删除状态. 1表示删除, 0表示未删除
    msg_device['other_one'] = ''    # 预留字段1
    msg_device['other_two'] = ''    # 预留字段2
    msg_device['create_time'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")      # 创建时间
    msg_device['update_time'] = data_dict['reporttime']     # 更新时间,将上报时间确定为更新时间
    msg_device['start'] = '07:30'        # 开始时间
    msg_device['end'] = '20:20'          # 结束时间
    msg_device['interval'] = '00:01'     # 上报间隔
    msg_device['i_machine'] = 1     # 定时开关井
    msg_device['h_machine'] = 0     # 手自动指示

    sql = "INSERT INTO device (code, `name`, factory, team, station, status, geo_x, geo_y, flag, other_one, other_two, create_time, update_time, start, `end`, `interval`, i_machine, h_machine) " \
          "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    data_list = [(msg_device['code'], msg_device['name'], msg_device['factory'], msg_device['team'], msg_device['station'],
                 msg_device['status'], msg_device['geo_x'], msg_device['geo_y'], msg_device['flag'], msg_device['other_one'],
                 msg_device['other_two'], msg_device['create_time'], msg_device['update_time'], msg_device['start'], msg_device['end'],
                 msg_device['interval'], msg_device['i_machine'], msg_device['h_machine'])]
    _cursor_execute_add_update(sql, data_list)
    update_wellid_to_deviceid()


# 2.更新  三种需要改的操作：(1)更新设备在线状态字段status; (2)更新update_time, i_machine, h_machine; (3)更新start, end, interval
# (1)更新设备在线状态字段status:设备上线时，离线时
def device_update_status(wellid, status):
    sql = "UPDATE device SET status = %s WHERE code = %s" % (status, wellid)
    _cursor_execute_add_update(sql)
    logging.debug("sqloperate:成功更新设备在线状态")


# (2)当服务器关闭时，更新所有设备的在线状态为离线状态0
def device_update_status_all():
    sql = "UPDATE device SET status=0 WHERE status=1"
    _cursor_execute_add_update(sql)
    logging.debug("sqloperate:成功更新设备离线状态")


# (3)更新update_time, h_machine
def device_update_property_1(d_id, data_dict):
    update_time = data_dict['reporttime']
    h_machine = data_dict['model']    # 自动/手动模式

    sql = "UPDATE device SET update_time = %s, h_machine = %s WHERE id = %s"
    data_list = [(update_time, h_machine, d_id)]
    _cursor_execute_add_update(sql, data_list)
    logging.debug("sqloperate:成功更新设备的update_time")


# (3)收到微信的控制命令后，更新update_time, start, end, interval, i_machine定时开关井：定时开井、定时关井
def device_update_property_2(data_dict):
    update_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wellid = data_dict['wellid']
    function_code = data_dict['function_code']
    if function_code == 0 or function_code == 1:    # 开关井定时打开/关闭
        start = "{}:{}".format('%02d' % data_dict['open_time'][0], '%02d' % data_dict['open_time'][1])
        end = "{}:{}".format('%02d' % data_dict['close_time'][0], '%02d' % data_dict['close_time'][1])
        i_machine = function_code
        sql = "UPDATE device SET update_time = %s, start = %s, end = %s, i_machine = %s WHERE code = %s"
        data_list = [(update_time, start, end, i_machine, wellid)]
        _cursor_execute_add_update(sql, data_list)

    if function_code == 2 or function_code == 3:    # 间隔上报打开/关闭
        interval = "{}:{}".format(
            '%02d' % data_dict['time_interval_timer'][0], '%02d' % data_dict['time_interval_timer'][1])
        sql = "UPDATE device SET update_time = %s, `interval` = %s WHERE code = %s"
        data_list = [(update_time, interval, wellid)]
        _cursor_execute_add_update(sql, data_list)

    # if function_code == 4 or function_code == 5:    # 立即开井/关井
        # 收到的控制命令中：4表示立即开井,5表示立即关井
        # 上报数据协议帧中：1表示开井状态,5表示关井状态
    #     pass
    #
    # if function_code == 6:      # 设定时间
    #     pass


# 3.查询1:井wellid是否已存在表device中
def device_get(wellid):
    """
    判断井wellid是否已存在表device中
    :param wellid:
    :return:True:已存在, False:不存在
    """
    sql = "SELECT count(*) FROM device WHERE code = %s" % wellid
    result = _cursor_execute_get(sql)   # tuple ((1,),)
    if result[0][0] == 0:
        return False
    else:
        return True


# 3.查询2:查询该设备是否已标记删除
def device_get_flag_deleted(wellid):
    """

    :param wellid:
    :return:True表示标记删除, False表示未标记删除
    """
    sql = "SELECT flag FROM device WHERE code = %s" % wellid
    result = _cursor_execute_get(sql)  # tuple ((1,),)
    if result[0][0] == 0:
        return False
    else:
        return True


# 3.查询3：查询该设备的station信息 [factory, team, station] ，返回给微信
def device_get_stationinfo(d_id):
    sql = "SELECT factory, team, station FROM device WHERE id = %s" % d_id
    result = _cursor_execute_get(sql)
    stationinfo = [result[0][0], result[0][1], result[0][2]]
    return stationinfo


# =========================================
# 表monitor的操作：增加
def monitor_add(sensor_list):
    sql = "INSERT INTO monitor (d_id, s_id, ss_id, s_name, `value`, create_time) " \
          "VALUES (%s, %s, %s, %s, %s, %s)"
    _cursor_execute_add_update(sql, sensor_list)


# =========================================
# 表sensor的操作：1.增加  2.更新  3.查询
# 1.增加
def sensor_add(sensor_list):
    sql = "INSERT INTO sensor " \
          "(d_id, ss_id, `name`, `value`, ex, flag, other_one, other_two, create_time, update_time, status, unit, " \
          "p3, p2, p1, p0, p_flag) " \
          "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    _cursor_execute_add_update(sql, sensor_list)


# 2.更新
def sensor_update(d_id, data_list):
    """
    更新传感器信息
    :param d_id:
    :param data_list:列表形式，[(value, ex, update_time, d_id, ss_id), ]
    :return:
    """
    sql = "UPDATE sensor SET `value` = %s, ex = %s, update_time = %s WHERE d_id = %s AND ss_id = %s"
    _cursor_execute_add_update(sql, data_list)


# 3.查询：查询传感器的激活状态、名称、单位等值
def sensor_get(d_id):
    """
    查询该设备的所有传感器的激活状态、名称、单位等值
    :param d_id:
    :return:
    """
    sensor_info = {}
    sql = "SELECT d_id, ss_id, `name`, flag, status, unit FROM sensor WHERE d_id = %s" % d_id
    result = _cursor_execute_get(sql)
    for res in result:
        sensor_info[res[1]] = res
    return sensor_info


# 3.查询：获取传感器当前的状态值，判断是否有状态改变
def sensor_get_state_change(d_id):
    sensor_info = {}
    sql = "SELECT d_id, ss_id, `name`, flag, status, unit FROM sensor WHERE d_id = %s" % d_id
    result = _cursor_execute_get(sql)
    for res in result:
        sensor_info[res[1]] = res
    return sensor_info


# 3.查询：查询ss_id对应的s_id
def sensor_get_ssid2sid(d_id):
    ssid2sid = {}
    sql = "SELECT id, ss_id FROM sensor WHERE d_id = %s" % d_id
    result = _cursor_execute_get(sql)
    for res in result:
        ssid2sid[res[1]] = res[0]
    return ssid2sid


# 3.查询：查询电流和电压的拟合参数
def sensor_get_pfit(d_id):
    pfit = {}
    sql = "SELECT ss_id, p3, p2, p1, p0 FROM sensor WHERE d_id = %s" % d_id
    result = _cursor_execute_get(sql)
    for res in result:
        pfit[res[0]] = res[1:]
    return pfit


# =========================================
# 表trigger的操作：1.增加  2.更新  3.查询
# 1.增加
def trigger_add(data_dict, d_id, ssid2sid):
    wellid = data_dict['wellid']
    create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_time = create_time
    alarm = 20      # 默认报警次数上限
    freq = 1

    sensor_01 = (d_id, ssid2sid[1], 1, '启停机', alarm, 0, '状态值', 0, 0, 0, '启机或停机', 1, 0, '', '', create_time, update_time, freq, wellid)
    sensor_02 = (d_id, ssid2sid[2], 2, '市电停来电', alarm, 0, '状态值', 0, 0, 0, '市电停电或来电', 1, 0, '', '', create_time, update_time, freq, wellid)
    sensor_03 = (d_id, ssid2sid[3], 3, '电池状态', alarm, 0, '状态值', 1, 0, 0, '电池电量低或正常', 1, 0, '', '', create_time, update_time, freq, wellid)
    sensor_04 = (d_id, ssid2sid[4], 4, '故障停状态', alarm, 0, '状态值', 1, 0, 0, '故障停或正常', 1, 0, '', '', create_time, update_time, freq, wellid)
    sensor_05 = (d_id, ssid2sid[5], 5, '皮带烧', alarm, 0, '状态值', 1, 0, 0, '皮带烧或皮带正常', 1, 0, '', '', create_time, update_time, freq, wellid)
    sensor_06 = (d_id, ssid2sid[6], 6, '曲柄销子', alarm, 0, '状态值', 1, 0, 0, '曲柄销子异常或正常', 1, 0, '', '', create_time, update_time, freq, wellid)
    sensor_07 = (d_id, ssid2sid[7], 7, '设备运行态', alarm, 0, '状态值', 0, 0, 0, '设备运行态正常或异常', 0, 0, '', '', create_time, update_time, freq, wellid)

    sensor_08 = (d_id, ssid2sid[8], 8, '上冲程电流', alarm, 0, '数值低于X高于Y', 30, 80, 0, '数值低于30高于80', 1, 0, '', '', create_time, update_time, freq, wellid)
    sensor_09 = (d_id, ssid2sid[9], 9, '下冲程电流', alarm, 0, '数值低于X高于Y', 8, 30, 0, '数值低于8高于30', 1, 0, '', '', create_time, update_time, freq, wellid)
    sensor_10 = (d_id, ssid2sid[10], 10, '运行电流', alarm, 0, '数值低于X高于Y', 0, 0, 0, '数值低于0高于0', 1, 0, '', '', create_time, update_time, freq, wellid)
    sensor_11 = (d_id, ssid2sid[11], 11, '平衡率', alarm, 0, '数值低于X高于Y', 80, 125, 0, '数值低于80%高于125%', 1, 0, '', '', create_time, update_time, freq, wellid)
    sensor_12 = (d_id, ssid2sid[12], 12, '油压', alarm, 0, '数值低于X高于Y', 0.5, 1.0, 0, '数值低于0.5高于1.0', 1, 0, '', '', create_time, update_time, freq, wellid)
    sensor_13 = (d_id, ssid2sid[13], 13, '套压', alarm, 0, '数值低于X高于Y', 0, 1.5, 0, '数值低于0高于1.5', 1, 0, '', '', create_time, update_time, freq, wellid)
    sensor_14 = (d_id, ssid2sid[14], 14, '回压', alarm, 0, '数值低于X高于Y', 0.5, 1.0, 0, '数值低于0.5高于1.0', 1, 0, '', '', create_time, update_time, freq, wellid)
    data_list = [sensor_01, sensor_02, sensor_03, sensor_04, sensor_05, sensor_06, sensor_07,
                 sensor_08, sensor_09, sensor_10, sensor_11, sensor_12, sensor_13, sensor_14]

    sql = "INSERT INTO `trigger` (d_id, s_id, ss_id, s_name, alarm, `current`, `type`, c_x, c_y, c_m, `desc`, " \
          "status, flag, other_one, other_two, create_time, update_time, freq, d_code) " \
          "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    _cursor_execute_add_update(sql, data_list)


# 2.更新：这部分代码暂时没写
def trigger_update(data):

    pass


# 3.查询：查询所有值
def trigger_get(d_id):
    sql = "SELECT id, ss_id, s_name, alarm, `current`, `type`, c_x, c_y, c_m, `desc`, status, flag, freq, d_code " \
          "FROM `trigger` WHERE d_id = %s" % d_id
    result = _cursor_execute_get(sql)
    trigger_info = {}
    for res in result:
        ss_id = res[1]
        trigger_info[ss_id] = res
    return trigger_info


# 表notify:增加  记录报警信息
def notify_add(data_list):
    sql = "INSERT INTO notify " \
          "(s_id, s_name, d_id, d_code, d_name, t_id, t_type, t_value, t_desc, remark, create_time) " \
          "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    _cursor_execute_add_update(sql, data_list)


def update_wellid_to_deviceid():
    # 更新井id和设备id的对应关系
    sql = "SELECT id, code FROM device"
    result = _cursor_execute_get(sql)       # result = ((1, 1), (2, 2), (3, 3))
    for id in result:
        wellid_deviceid[id[1]] = id[0]
    logging.debug("已更新id对应关系，wellid:d_id = {}".format(wellid_deviceid))


def deviceid_of_wellid(wellid):
    if wellid in wellid_deviceid:
        d_id = wellid_deviceid[wellid]
        return d_id
    return None


def _cursor_execute_add_update(sql, data_list=None):
    """
    执行数据库的增加和更新操作，data_list不为None表示一次插入多行数据
    :param sql:
    :param data_list: 是一个列表，列表中的每一个元素必须是元组,eg:[(1,2,3), (1,2,3), (1,2,3)]
    :return:
    """
    try:
        db = pymysql.connect(host, username, password, database_name)
        cursor = db.cursor()

        if data_list is None:
            cursor.execute(sql)
        else:
            cursor.executemany(sql, data_list)
        db.commit()
        # logging.debug("[ sql store successful ]")
    except Exception as ex:
        db.rollback()
        logging.error("--store failed!")
        logging.error(ex)
    finally:
        db.close()

    # try:
    #     if data_list is None:
    #         cursor.execute(sql)
    #     else:
    #         cursor.executemany(sql, data_list)
    #     db.commit()
    #     logging.info("--store successful!")
    # except Exception as err:
    #     # 如果发生错误则回滚
    #     db.rollback()
    #     logging.error("--store failed!")
    #     logging.error(err)
    # finally:
    #     db.close()


def _cursor_execute_get(sql):
    db = pymysql.connect(host, username, password, database_name)
    cursor = db.cursor()

    cursor.execute(sql)
    results = cursor.fetchall()  # 返回的结果是分组的结果，第1组的值即为所需
    db.close()
    return results

    # try:
    #     cursor.execute(sql)
    #     results = cursor.fetchall()  # 返回的结果是分组的结果，第1组的值即为所需
    # except Exception as err:
    #     # 如果发生错误则回滚
    #     db.rollback()
    #     logging.error("--get failed!")
    #     logging.error(err)
    #     results = None
    # db.close()
    # return results
