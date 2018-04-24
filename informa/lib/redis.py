import collections
import datetime
import decimal

import pytz
import redis


class TempHumidRedis():
    def __init__(self, host, port):
        self.redis_ = redis.StrictRedis(host, port)


    def append(self, temperature, humidity):
        """
        APPEND ts/temp/humid in redis keyed by today
        """
        #TODO temp/humid can't be >100

        # timestamp of data point
        ts = int(datetime.datetime.now().timestamp())

        # generate PK from today's date
        pk = datetime.date.today().strftime('%y%m%d')

        self.redis_.append(
            pk, '{}{:0>4.1f}{:0>4.1f}'.format(ts, temperature, humidity)
        )


    def get_day(self, date):
        """
        Given a datetime.date (or date string) return a dict of the day's data
        """
        if type(date) is datetime.date:
            date = date.strftime('%y%m%d')

        day_of_data = self.redis_.get(date)

        if not day_of_data:
            return []

        output = collections.OrderedDict()

        DATA_POINT_LEN = 18

        for i in range(0, int(len(day_of_data) / 18)):
            item = day_of_data[(i*18):((i+1)*18)].decode('ascii')

            output[int(item[0:10])] = {
                'temp': decimal.Decimal(item[10:14]),
                'humid': decimal.Decimal(item[14:18]),
            }

        return output
