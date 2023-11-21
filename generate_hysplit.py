# -*- coding: utf-8 -*-
"""
Created on Thu Dec 30 09:54:31 2021

@author: hilario

Package for generating HYSPLIT trajectories

Command on Anaconda Prompt: python {full script location}
(e.g., python C:\\Users\hilario\OneDrive - University of Arizona\Python\CAMP2ExSourceTraj\product_trajectories\scripts\product_auto_hysplit_P3.py)

Requires:
    1. Input data as a dataframe (lat, lon, time as datetime, altitude as meters AGL)
    2. Directories
        - storage_dir: where output files (trajectories) will be saved. Default is a subfolder under C:\\trajectories
        - meteo_dir: where meteorological input data is stored (e.g., GFS)
    3. Parameters
        - basename: a unique label (e.g., AfricanDust)
        - runtime: how long trajectories will be run for. Negative value means backward trajectories
        - dataset: which meteorological input data to use (e.g., GFS, NCEP, GDAS)
        - ceiling height: default 15,000 m AGL
        - vertmot: 0 means use vertical wind from model data
        - addMeteo: True if I want to add meteorology along trajectories in output files
"""

import os
import pandas as pd
import shutil
from subprocess import call
import numpy as np
import calendar
import fnmatch
import datetime as dt
import multiprocessing as mp

'''Directories'''
hysplit_dir = 'C:\\hysplit4\\exec\\hyts_std'
working_dir = 'C:\\hysplit4\\working\\'

'''Runs HYSPLIT'''
def run_hysplit(year, month, day, hour, minute, altitude, location, params, add_met = True):
    meteofiles = getMet(year, month, day, params)
    os.chdir(params['new_working'])
    # this generates the control file in the workPath directory
    ctrlFile(location, year, month, day, hour, minute, altitude, meteofiles, params)
    #adds meteorological data from dataset to output trajectory files    
    if add_met:
        addMeteoOutput(tm_pres = 1, tm_tpot = 1, tm_tamb = 1, tm_rain = 1,
                   tm_mixd = 1, tm_relh = 1, tm_sphu = 1, tm_mixr = 1, 
                   tm_dswf = 1, tm_terr = 1)
    call(hysplit_dir)
    shutil.move(params['trajName'], params['storage_dir'] + params['trajName'])

'''Gets meteorological data based on timestamp'''
def getMet(year, month, day, params):
    dataset, meteo_dir, runtime = params['dataset'], params['meteo_dir'], params['runtime']
    #for each date, want to collect the meteorology file for that week + preceding + subsequent weeks
    meteofiles = []
    month = int(month)
    
    if dataset == 'gdas': #gdas1.apr19.w1
        #given the day, figure out what week it is in
        week = int(np.ceil(int(day)/7))
        nowStr = '*%s*%s*%s' % (calendar.month_abbr[month].lower(), str(year)[2:4], week)
        if (week+1) > 5:
            nextStr = '*%s*%s*%s' % (calendar.month_abbr[month+1].lower(), str(year)[2:4], 1)
        else:
            nextStr = '*%s*%s*%s' % (calendar.month_abbr[month].lower(), str(year)[2:4], week+1)
        if (week-1) < 1:
            lastStr = '*%s*%s*%s' % (calendar.month_abbr[month-1].lower(), str(year)[2:4], 5)
            last2Str = '*%s*%s*%s' % (calendar.month_abbr[month-1].lower(), str(year)[2:4], 4)
        else:
            lastStr = '*%s*%s*%s' % (calendar.month_abbr[month].lower(), str(year)[2:4], week-1)
            last2Str = '*%s*%s*%s' % (calendar.month_abbr[month].lower(), str(year)[2:4], week-2)
        try:
            os.chdir(meteo_dir)
            #Gets list of files in meteo_dir
            _, _, files = next(os.walk('.'))
            #Adds relevant files to list of meteofiles
            for f in files:
                if fnmatch.fnmatch(f, nowStr):
                    meteofiles.append(f)
                elif fnmatch.fnmatch(f, lastStr):
                    meteofiles.append(f)
                elif fnmatch.fnmatch(f, last2Str):
                    meteofiles.append(f)
                elif fnmatch.fnmatch(f, nextStr):
                    meteofiles.append(f)
        except:
            print('getMet Error')
    
    elif dataset == 'gfs':#20190930_gfs0p25
        nowStr = '%s%s%s' % (year, str(month).zfill(2), str(day).zfill(2))
        buffer_day, runtime_days = dt.timedelta(days=0), dt.timedelta(days=int(abs(runtime/24))+1)
        if runtime > 0: #if forward trajectory
            date_range = pd.date_range(pd.to_datetime(nowStr)-buffer_day, 
                                       pd.to_datetime(nowStr)+runtime_days)
        else: #if backward trajectory
            date_range = pd.date_range(pd.to_datetime(nowStr)-runtime_days,
                                       pd.to_datetime(nowStr)+buffer_day)
        
        meteofiles = list(set([f'{i.strftime("%Y%m%d")}_gfs0p25' for i in date_range]))
    
    elif dataset == 'ncep':#20190930_gfs0p25
        # nowStr, nextStr, lastStr
        nowStr = '%s%s%s' % (year, str(month).zfill(2), str(day).zfill(2))
        #Getting next days
        nextStr = pd.date_range(nowStr, pd.to_datetime(nowStr)+dt.timedelta(days=int(abs(runtime/24))+1))
        nextStr = [i.strftime('%Y%m') for i in nextStr]
        #Getting previous days
        lastStr = pd.date_range(pd.to_datetime(nowStr)-dt.timedelta(days=int(abs(runtime/24))+1), nowStr)
        lastStr = [i.strftime('%Y%m') for i in lastStr]
        #After we get next and previous days, reformat nowStr to YYYYMM 
        nowStr = nowStr[:6]
        #Compiling list of data needed
        for i in [lastStr, nowStr, nextStr]:
            if isinstance(i, pd.DatetimeIndex):
                i=i.tolist()
            elif not isinstance(i, list):
                i=[i]
            meteofiles+=i
        #Removing duplicates, setting to filename
        meteofiles = list(set([f'RP{i}.gbl' for i in meteofiles]))
        
    elif dataset == 'nam': #20120518_hysplit.t00z.namsa
        # nowStr, nextStr, lastStr
        nowStr = '%s%s%s' % (year, str(month).zfill(2), str(day).zfill(2))
        buffer_t, delta_t = dt.timedelta(days=1), dt.timedelta(days=int(abs(runtime/24))+1)
        if runtime > 0: #if forward trajectory
            date_range = pd.date_range(pd.to_datetime(nowStr)-buffer_t, 
                                       pd.to_datetime(nowStr)+delta_t)
        else: #if backward trajectory
            date_range = pd.date_range(pd.to_datetime(nowStr)-delta_t,
                                       pd.to_datetime(nowStr)+buffer_t)
        meteofiles = list(set([f'{i.strftime("%Y%m%d")}_hysplit.t00z.namsa' for i in date_range]))
        # meteofiles = ['20120518_hysplit.t00z.namsa'] #for testing only
    else:
        print(f'Script does not know how to handle {dataset}. Update needed on getMet().')
    return meteofiles

'''Setup of the control file prior to HYSPLIT run'''
# def ctrlFile(location, year, month, day, hour, minute, altitude, meteo_dir,
#               meteofiles, runtime, trajName, ceiling, vertmot):
def ctrlFile(location, year, month, day, hour, minute, altitude, meteofiles, params):
    meteo_dir, runtime, trajName, ceiling, vertmot = params['meteo_dir'], params['runtime'], params['trajName'], params['ceiling'], params['vertmot']
    controltext = ['%s %s %s %s %s\n' % (year, month.zfill(2), day.zfill(2), hour.zfill(2), minute.zfill(2)),
                    '1\n',
                    '{0!s} {1!s} {2!s}\n'.format(location[0], location[1], altitude),
                    '{0!s}\n'.format(runtime),
                    '{0!s}\n'.format(vertmot), #for isobaric, pick 1
                    '{0!s}.0\n'.format(ceiling), #default model top
                    '{0!s}\n'.format(len(meteofiles))]
        
    for f in meteofiles:
        controltext.append('{0}\n'.format(meteo_dir))
        controltext.append('{0}\n'.format(f))

    controltext.append('./\n')
    controltext.append('{0}\n'.format(trajName))

    with open('CONTROL', 'w') as control:
        control.writelines(controltext)

'''Creates SETUP.CFG to add meteorological columns to output trajectory files'''
def addMeteoOutput(tm_pres, tm_tpot, tm_tamb, tm_rain, tm_mixd, tm_relh, tm_sphu, tm_mixr, tm_dswf, tm_terr):
     #set to 1 if add meteorological data to trajectory output files
     #Meteorological variables:
         #pres = pressure (hPa), tpot = potential temperature (K), tamb = ambient temperature (K), 
         #rain = precipitation (mm h-1), mixd = mixing depth (m), relh = relative humidity (%), 
         #sphu = specific humidity (g/kg air), mixr = water vapor mixing ratio (g/kg dry-air),
         #dswf = downward solar radiation flux (W m-2), terr = terrain height (m)
     #Source: https://www.ready.noaa.gov/hysplitusersguide/S614.htm
     # tm_pres = 1; tm_tpot = 1; tm_tamb = 1; tm_rain = 1;tm_mixd = 1; tm_relh = 1; tm_sphu = 1; tm_mixr = 1; tm_dswf = 1; tm_terr = 1
     setuptext = ['&SETUP\n',
                 'tratio = 0.75,\n',
                 'mgmin = 10,\n',
                 'khmax = 9999,\n',
                 'kmixd = 0,\n',
                 'kmsl = 0,\n',
                 'nstr = 0,\n',
                 'mhrs = 9999,\n',
                 'nver = 0,\n',
                 'tout = 60,\n',
                 f'tm_tpot = {tm_tpot},\n',
                 f'tm_tamb = {tm_tamb},\n',
                 f'tm_rain = {tm_rain},\n',
                 f'tm_mixd = {tm_mixd},\n',
                 f'tm_relh = {tm_relh},\n',
                 f'tm_sphu = {tm_sphu},\n',
                 f'tm_mixr = {tm_mixr},\n',
                 f'tm_dswf = {tm_dswf},\n',
                 f'tm_terr = {tm_terr},\n',
                 'dxf = 1.0,\n',
                 'dyf = 1.0,\n', 
                 'dzf = 0.01,\n',
                 'wvert = .FALSE.,\n',
                 '/']
     with open('SETUP.CFG', 'w') as setup:
        setup.writelines(setuptext)

'''Edits default_exec to set new working directory - done so no need to repeat this'''
def transfer_defaults(working_dir, n):
    working_files = os.listdir(working_dir)
    '''Generates new working_dir so HYSPLIT can working in multiple places'''
    new_working = '%s%s\\' % (working_dir[:-1],n)
    if not os.path.exists(new_working): 
        os.mkdir(new_working) #creates temporary working_dir
    for file in working_files:
        if file.startswith('default'):
            shutil.copy(working_dir + file, new_working + file)
    df = pd.read_csv(new_working + '\\default_exec')
    df.loc[13] = new_working.replace('\\','/')[:-1]
    df.loc[26] = new_working.replace('\\','/')[:-1]
    df.to_csv(new_working + '\\default_exec')
    # df = pd.read_csv(new_working + '\\SETUP.CFG')

def parallel_hysplit(input_data):
    # n, data, params = 1, fragments[0], info.copy() #for testing
    n, data, params =  input_data
    new_working = '%s%s\\' % (working_dir[:-1],n)
    params['new_working'] = new_working
    
    for i in data.index:
        date = data.loc[i, params['time_col']]
        lon = data.loc[i, params['lon_col']]
        lat = data.loc[i, params['lat_col']]
        altitude = data.loc[i, params['alt_col']]
        year = str(date.year)
        month = str(date.month).zfill(2)
        day = str(date.day).zfill(2)
        hour = str(date.hour).zfill(2)
        minute = str(date.minute).zfill(2)
        trajName = f'{params["basename"]}_{year}{month}{day}{hour}{minute}' #%s_%s%s%s%s%s_la' % (basename, y, m, d, H, M, lat, lon)
        params['trajName'] = trajName
        run_hysplit(year, month, day, hour, minute, altitude, (lat, lon), params)
            #prep_input(skip_done = True) already filters out existing trajectories from coords
            
def prep_input(coords, info, skip_done = True, n_cores = mp.cpu_count()):
    basename, storage_dir = info['basename'], info['storage_dir']
    print(f'Total number of trajectories: {len(coords)}')
    if skip_done: #skip_done: If I want to skip over existing trajectories
        traj_list = os.listdir(storage_dir)
        to_process = [i for i in coords['Date_Time_UTC'] if f'{basename}_{i.strftime("%Y%m%d%H%M")}' not in traj_list]                    
        print(f'# trajectories done: {len(coords)-len(to_process)}')
        coords = coords.loc[coords['Date_Time_UTC'].isin(to_process)]
        
    print(f'# trajectories to make: {len(coords)}')
    #Chunks input data for parallelization
    fragments = np.array_split(coords, n_cores) #fragments data so I can work in parallel
    return fragments

def run(coords, lat_col, lon_col, alt_col, time_col, project, dataset, meteo_dir,
        runtime = -72, vertmot = 0, ceiling = 10000, skip_done = True, n_cores = mp.cpu_count()):
    
    print('Trying to run')
    coords.reset_index(inplace=True)

    '''HYSPLIT parameters'''
    info = {'basename': f'{project}_{dataset.upper()}_{abs(runtime)}h', 
            'meteo_dir': meteo_dir, 
            'runtime': runtime, 
            'vertmot': vertmot, 
            'ceiling': ceiling,
            'lat_col': lat_col, 
            'lon_col': lon_col, 
            'alt_col': alt_col,
            'time_col': time_col, 
            'dataset': dataset,
            'project': project}
    info['storage_dir'] = f'C:\\trajectories\\{info["basename"]}\\'
    
    if not os.path.exists(info['storage_dir']): 
        os.mkdir(info['storage_dir'])

    for n in range(n_cores):
        transfer_defaults(working_dir, n+1)
        
    print('Chunking input data')
    fragments = prep_input(coords, info.copy(), skip_done)
    
    print('Starting parallelized HYSPLIT')
    pool = mp.Pool(n_cores)
    pool.map_async(parallel_hysplit, [(n+1, df, info.copy()) for n, df in enumerate(fragments)])
    pool.close()
    pool.join() 

def read_traj(filename, storage_dir):
    with open(storage_dir+filename) as f:
        content = f.readlines()
    content = [x.strip() for x in content]
    skiprows = int(content[0].split(' ')[0])+4
    traj = pd.read_csv(storage_dir+filename, skiprows = skiprows, header = None, delim_whitespace = True)
    traj = traj.iloc[:, 2:]
    traj.columns = ['Year', 'Month', 'Day', 'Hour', 'Min', '',
                    'Timestep', 'Latitude', 'Longitude', 'Altitude_AGL_m', 
                    'Pressure_mb','tpot', 'tamb',
                    'rain', 'mixd', 'relh', 'sphu',
                    'mixr','dswf','terr']
    traj['Launch_UTC'] = pd.to_datetime(f'{traj.Year.iloc[0].astype(str)}'
                                    f'{traj.Month.iloc[0].astype(str).zfill(2)}'
                                    f'{traj.Day.iloc[0].astype(str).zfill(2)}'
                                    f'{traj.Hour.iloc[0].astype(str).zfill(2)}'
                                    f'{traj.Min.iloc[0].astype(str).zfill(2)}',
                                    format = '%y%m%d%H%M')
    traj.drop(columns = ['Year', 'Month', 'Day', 'Hour', 'Min', ''],inplace=True)
    traj['Launch_Altitude_AGL_m'] = traj.Altitude_AGL_m[0]
    return traj

def compile_traj(traj_list, storage_dir):
    return pd.concat([read_traj(traj, storage_dir) for traj in traj_list])