# -*- coding: UTF-8 -*-
from server_comm import sqloperate, data_process

if __name__ == '__main__':
    sqloperate.device_update_status_all()
    data_process.stop_service_inform()
