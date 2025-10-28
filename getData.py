#!/usr/bin/python

import scdata as sc
from scdata._config import config
import asyncio
import pickle

DEVICE_ID=15695

print(f"Getting all data for device #{DEVICE_ID}...")

# Set verbose level
config.log_level = 'DEBUG'

# Device id needs to be as str
device = sc.Device(blueprint='sc_air',
                               params=sc.APIParams(id=DEVICE_ID))
device.options.min_date = None #Don't trim min_date
device.options.max_date = None #Don't trim max_date
#device.options.frequency = '1Min' # Use this to change the sample frequency for the request
#print (device.json)

# Load
asyncio.run(device.load())

#print (device.json)
#print (device.data)
#print (device.data.columns.values.tolist())

#device.data.to_csv(f"SCK_{DEVICE_ID}.csv", sep='\t', encoding='utf-8', index=False, header=True)

outfile = open(f'SCK_{DEVICE_ID}.pk', 'wb')
pickle.dump(device.data, outfile)
outfile.close()
