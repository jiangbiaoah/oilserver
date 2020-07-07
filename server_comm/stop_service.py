# -*- coding: UTF-8 -*-
import sqloperate
import data_process

if __name__ == '__main__':
    sqloperate.device_update_status_all()
    data_process.stop_service_inform()
