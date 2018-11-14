import csv
import math
import numpy as np
import os
from pandas import DataFrame, concat


class Scale(object):
    '''
    Given max and min of a rectangle it computes the scale and shift values to normalize data to [0,1]
    '''

    def __init__(self):
        self.min_x = +math.inf
        self.max_x = -math.inf
        self.min_y = +math.inf
        self.max_y = -math.inf
        self.sx, self.sy = 1, 1

    def calc_scale(self, keep_ratio=True):
        self.sx = 1 / (self.max_x - self.min_x)
        self.sy = 1 / (self.max_y - self.min_y)
        if keep_ratio:
            if self.sx > self.sy:
                self.sx = self.sy
            else:
                self.sy = self.sx

    def normalize(self, data, shift=True, inPlace=True):
        if inPlace:
            data_copy = data
        else:
            data_copy = np.copy(data)

        if shift:
            data_copy[:, 0] = (data[:, 0] - self.min_x) * self.sx
            data_copy[:, 1] = (data[:, 1] - self.min_y) * self.sy
        else:
            data_copy[:, 0] = data[:, 0] * self.sx
            data_copy[:, 1] = data[:, 1] * self.sy
        return data_copy

    def denormalize(self, data, shift=True, inPlace=False):
        if inPlace:
            data_copy = data
        else:
            data_copy = np.copy(data)

        ndim = data.ndim
        if ndim == 1:
            data_copy[0] = data[0] / self.sx + self.min_x * shift
            data_copy[1] = data[1] / self.sy + self.min_y * shift
        elif ndim == 2:
            data_copy[:, 0] = data[:, 0] / self.sx + self.min_x * shift
            data_copy[:, 1] = data[:, 1] / self.sy + self.min_y * shift
        elif ndim == 3:
            data_copy[:, :, 0] = data[:, :, 0] / self.sx + self.min_x * shift
            data_copy[:, :, 1] = data[:, :, 1] / self.sy + self.min_y * shift

        return data_copy


class BIWIParser:
    def __init__(self):
        self.scale = Scale()
        self.all_ids = list()
        self.actual_fps = 0.

    def load(self, filename, down_sample=1):
        pos_data_dict = dict()
        vel_data_dict = dict()
        time_data_dict = dict()
        self.all_ids.clear()

        # check to search for many files?
        file_names = list()
        if '*' in filename:
            files_path = filename[:filename.index('*')]
            extension = filename[filename.index('*') + 1:]
            for file in os.listdir(files_path):
                if file.endswith(extension):
                    file_names.append(files_path + file)
        else:
            file_names.append(filename)

        self.actual_fps = 2.5
        for file in file_names:
            with open(file, 'r') as data_file:
                content = data_file.readlines()
                id_list = list()
                for row in content:
                    row = row.split(' ')
                    while '' in row: row.remove('')
                    if len(row) != 8: continue

                    ts = float(row[0])
                    id = round(float(row[1]))
                    if ts % down_sample != 0:
                        continue

                    px = float(row[2])
                    py = float(row[4])
                    vx = float(row[5])
                    vy = float(row[7])

                    if id not in id_list:
                        id_list.append(id)
                        pos_data_dict[id] = list()
                        vel_data_dict[id] = list()
                        time_data_dict[id] = np.empty(0, dtype=int)
                        last_t = ts
                    pos_data_dict[id].append(np.array([px, py]))
                    vel_data_dict[id].append(np.array([vx, vy]))
                    time_data_dict[id] = np.hstack((time_data_dict[id], np.array([ts])))
            self.all_ids += id_list

        p_data = list()
        v_data = list()
        t_data = list()

        for key, value in pos_data_dict.items():
            poss_i = np.array(value)
            p_data.append(poss_i)
            # TODO: you can apply a Kalman filter/smoother on v_data
            vels_i = np.array(vel_data_dict[key])
            v_data.append(vels_i)
            t_data.append(np.array(time_data_dict[key]))

        for i in range(len(p_data)):
            poss_i = np.array(p_data[i])
            self.scale.min_x = min(self.scale.min_x, min(poss_i[:, 0]))
            self.scale.max_x = max(self.scale.max_x, max(poss_i[:, 0]))
            self.scale.min_y = min(self.scale.min_y, min(poss_i[:, 1]))
            self.scale.max_y = max(self.scale.max_y, max(poss_i[:, 1]))
        self.scale.calc_scale()

        return p_data, v_data, t_data


class SeyfriedParser:
    def __init__(self):
        self.scale = Scale()
        self.actual_fps = 0.

    def load(self, filename, down_sample=4):
        '''
        Loads datas of seyfried experiments
        * seyfried template:
        >> n_Obstacles
        >> x1[i] y1[i] x2[i] y2[i] x(n_Obstacles)
        >> fps
        >> id, timestamp, pos_x, pos_y, pos_z
        >> ...
        :param filename: dataset file with seyfried template
        :param down_sample: To take just one sample every down_sample
        :return:
        '''
        pos_data_list = list()
        vel_data_list = list()
        time_data_list = list()

        # check to search for many files?
        file_names = list()
        if '*' in filename:
            files_path = filename[:filename.index('*')]
            extension = filename[filename.index('*')+1:]
            for file in os.listdir(files_path):
                if file.endswith(extension):
                    file_names.append(files_path+file)
        else:
            file_names.append(filename)

        for file in file_names:
            with open(file, 'r') as data_file:
                csv_reader = csv.reader(data_file, delimiter=' ')
                id_list = list()
                i = 0
                for row in csv_reader:
                    i += 1
                    if i == 4:
                        fps = float(row[0])
                        self.actual_fps = fps / down_sample

                    if len(row) != 5:
                        continue

                    id = row[0]
                    ts = float(row[1])
                    if ts % down_sample != 0:
                        continue

                    px = float(row[2])/100.
                    py = float(row[3])/100.
                    pz = float(row[4])/100.
                    if id not in id_list:
                        id_list.append(id)
                        pos_data_list.append(list())
                        vel_data_list.append(list())
                        time_data_list.append(np.empty((0), dtype=int))
                        last_px = px
                        last_py = py
                        last_t = ts
                    pos_data_list[-1].append(np.array([px, py]))
                    v = np.array([px - last_px, py - last_py]) * fps / (ts - last_t + np.finfo(float).eps)
                    vel_data_list[-1].append(v)
                    time_data_list[-1] = np.hstack((time_data_list[-1], np.array([ts])))

                    # FIXME: uncomment if you need instant velocity
                    #last_px = px
                    #last_py = py
                    #last_t = ts

        p_data = list()
        v_data = list()

        for i in range(len(pos_data_list)):
            poss_i = np.array(pos_data_list[i])
            p_data.append(poss_i)
            # TODO: you can apply a Kalman filter/smoother on v_data
            vels_i = np.array(vel_data_list[i])
            v_data.append(vels_i)
        t_data = np.array(time_data_list)

        for i in range(len(pos_data_list)):
            poss_i = np.array(pos_data_list[i])
            self.scale.min_x = min(self.scale.min_x, min(poss_i[:, 0]))
            self.scale.max_x = max(self.scale.max_x, max(poss_i[:, 0]))
            self.scale.min_y = min(self.scale.min_y, min(poss_i[:, 1]))
            self.scale.max_y = max(self.scale.max_y, max(poss_i[:, 1]))
        self.scale.calc_scale()

        return p_data, v_data, t_data


def to_supervised(data, n_in=1, n_out=1, diff_in=False, diff_out=True, drop_nan=True):
    '''
    @CopyRight: Code is inspired by weblog of machinelearningmastery.com
    Copies the data columns (of an nD sequence) so that for each timestep you have a "in" seq and an "out" seq
    :param data:
    :param n_in: length of "in" seq (number of observations)
    :param n_out: length of "out" seq (number of predictions)
    :param diff_in: if True the "in" columns are differential otherwise will be absolute
    :param diff_out: if True the "out" columns are differential otherwise will be absolute
    :param drop_nan: if True eliminate the samples that contains nan (due to shift operation)
    :return: a table whose columns are n_in * nD (observations) and then n_out * nD (predictions)
    '''

    n_vars = 1 if type(data) is list else data.shape[1]
    df = DataFrame(data)
    cols, names = list(), list()

    # input sequence (t-n, ... t-1)
    for i in range(n_in, 0, -1):
        names += [('var_in%d(t-%d)' % (j + 1, i-1)) for j in range(n_vars)]
        if diff_in:
            cols.append(df.shift(i-1) - df.shift(i))
        else:
            cols.append(df.shift(i-1))

    # forecast sequence (t, t+1, ... t+n)
    for i in range(1, n_out+1):
        names += [('var_out%d(t+%d)' % (j + 1, i)) for j in range(n_vars)]
        if diff_out:
            cols.append(df.shift(-i) - df.shift(0))  # displacement
        else:
            cols.append(df.shift(-i))  # position

    # put it all together
    agg = concat(cols, axis=1)
    agg.columns = names

    # drop rows with NaN values
    if drop_nan:
        agg.dropna(inplace=True)

    return agg.values

