import pandas as pd
import requests
import os
import zlib
import shutil
from multiprocessing import  Pool
from functools import partial
import numpy as np
import time
from tqdm import tqdm

# https://stackoverflow.com/questions/26784164/pandas-multiprocessing-apply
def parallelize(data, func, num_of_processes, **kwargs):
    data_split = np.array_split(data, 10000)
    print(len(data_split), "parts", len(data_split[0]), "images per part, on", num_of_processes, "processes", 2, "parts in chunk.")
    
    results = []
    with Pool(num_of_processes) as pool:
        for i, df_ in enumerate(pool.imap_unordered(func, data_split, 2)):
            results.append(df_)
            img_progress.update(len(df_))
    data = pd.concat(results, ignore_index=True)
    return data

def run_on_subset(func, data_subset):
    return data_subset.apply(func, axis=1)

def parallelize_on_rows(data, func, num_of_processes):
    return parallelize(data, partial(run_on_subset, func), num_of_processes)

def download_image(row):
    # Unique name based on url
    fname = "%s/%s" % (row['folder'], (zlib.crc32(row['url'].encode('utf-8')) & 0xffffffff))

    # Skip Already downloaded, retry others later
    if os.path.isfile(fname):
        row['status'] = 200
        row['file'] = fname
        return row

    try:
        # use smaller timeout to skip errors, but can result in failed downloads
        # stream=True and shutil uses less memory but also can cause incomplete downloads
        response = requests.get(row['url'], stream=False, timeout=5) 
    except:
        # log errors later, set error as 408 timeout
        row['status'] = 408
        return row
    
    row['status'] = response.status_code
    if response.ok:
        try:
            with open(fname, 'wb') as out_file:
                # some sites respond with gzip transport encoding
                response.raw.decode_content = True
                #shutil.copyfileobj(response.raw, out_file)
                out_file.write(response.content)
        except:
            # This is if it times out during a download
            row['status'] = 408
            return row        
        
        row['file'] = fname

    return row

def open_tsv(fname, folder):
    print("Opening %s Data File..." % fname)
    df = pd.read_csv(fname, sep='\t', names=["caption","url"], usecols=range(1,2))
    df['folder'] = folder
    df['status'] = None
    df['file'] = None
    np.random.shuffle(df.values)
    print("Processing", len(df), " Images:")
    return df

df = open_tsv("Validation_GCC-1.1.0-Validation.tsv","validation")
img_progress = tqdm(desc="Downloading...", total=len(df), position=0)
df = parallelize_on_rows(df, download_image, 64) # number of processes in the pool can be larger than cores
df.to_csv("downloaded_validation_report.tsv", sep='\t', header=False, index=False)

df = open_tsv("Train_GCC-training.tsv","training")
img_progress = tqdm(desc="Downloading...", total=len(df), position=0)
df = parallelize_on_rows(df, download_image, 64) # number of processes in the pool can be larger than cores
df.to_csv("downloaded_training_report.tsv", sep='\t', header=False, index=False)
