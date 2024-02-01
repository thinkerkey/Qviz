from Oviz.Utils.common_utils import *
from Oviz.Utils.point_cloud_utils import read_pcd, read_bin
from Oviz.log_sys import send_log_msg
import os
import cv2
from Oviz.PointPuzzle.uos_pcd import UOSLidarData
import threading

class Model(QObject):
    hasNewMsg = Signal(float)
    def __init__(self):
        super().__init__()
        self.stop = False
        self.offline_frame_cnt = 0
        self.data_frame_list = []
        self.database = {}
        self.curr_frame_data = {}
        self.uos_lidar_type = False

    def online_callback(self, msg):
        # print(msg)
        self.curr_frame_data = msg['data']
        self.hasNewMsg.emit(msg['timestamp'])

    def get_curr_frame_data(self, index):
        if index >= self.offline_frame_cnt: return 0
        key = self.data_frame_list[index]
        self.curr_frame_data = {}

        for group, subdatabase  in self.database.items():
            self.curr_frame_data[group] = {}
            for topic_type, values in subdatabase.items():
                self.curr_frame_data[group][topic_type] = []
                for value in values:
                    if key in value.keys():
                        if topic_type == POINTCLOUD and self.uos_lidar_type:
                            data_path = index
                        else:
                            data_path = value[key]
                        parse_data = eval("self.smart_read_%s"%topic_type)(data_path)
                        self.curr_frame_data[group][topic_type].append(parse_data)

        return key

    def remove_sub_database(self, key_str):
        try:
            self.database.pop(key_str)
            self.curr_frame_data.pop(key_str)
        except:
            pass

    def remove_sub_element_database(self, group, ele_key, index):
        try:
            self.database[group][ele_key].pop(index)
            self.curr_frame_data[group][ele_key].pop(index)
        except:
            pass

    def smart_read_pointcloud(self, pc_path):
        if self.uos_lidar_type:
            pc = self.uos_lidar_data.get_frame_pcd(pc_path)
            return pc
        if pc_path.endswith(".pcd"):
            pc = read_pcd(pc_path)
        elif pc_path.endswith(".bin"):
            pc = read_bin(pc_path)
        return pc

    def smart_read_image(self, image_path):
        img = cv2.imread(image_path)
        return img

    def deal_image_folder(self, group, folder_path, ele_index):
        if self.uos_lidar_type:
            if self.offline_frame_cnt > 0:
                cnt = self.offline_frame_cnt
                image_list, timestamp_list = find_files_with_extension(folder_path)
                target_timestamp_list = self.uos_lidar_data.navi_list[:, 0]
                latest_database = {}

                for i, lidar_t in enumerate(target_timestamp_list):
                    min_time_difference = float('inf')
                    for j, img_t in enumerate(timestamp_list):
                        time_difference = abs(img_t - lidar_t)
                        if time_difference > 1.0: continue
                        if time_difference < min_time_difference:
                            min_time_difference = time_difference
                            key = str(i).zfill(6)
                            latest_database[key] = image_list[j]
                            if time_difference < 0.5:
                                break

                group_data = self.database.setdefault(group, {})
                topic_data = group_data.setdefault(IMAGE, [])

                if ele_index < len(topic_data):
                    topic_data[ele_index] = latest_database
                else:
                    topic_data.append(latest_database)
                # import ipdb
                # ipdb.set_trace()
        else:
            cnt = self.deal_folder(group, folder_path, ele_index, IMAGE, [".jpg", ".png", ".tiff"])
        return cnt

    def deal_pointcloud_folder(self, group, folder_path, ele_index):
        ml_lidar_state_path = os.path.join(folder_path, "ml_lidar_state")
        if os.path.exists(ml_lidar_state_path):
            self.uos_lidar_type = True
            self.uos_lidar_data = UOSLidarData(folder_path)
            cnt = self.uos_lidar_data.framecnt

            latest_database = {}

            for i in range(cnt):
                key = str(i).zfill(6)
                latest_database[key] = i

            if cnt > 0:
                self.data_frame_list = sorted(latest_database.keys())
                self.offline_frame_cnt = cnt

                group_data = self.database.setdefault(group, {})
                topic_data = group_data.setdefault(POINTCLOUD, [])

                if ele_index < len(topic_data):
                    topic_data[ele_index] = latest_database
                else:
                    topic_data.append(latest_database)

        else:
            self.uos_lidar_type = False
            cnt = self.deal_folder(group, folder_path, ele_index, POINTCLOUD, [".pcd", ".bin"])
        return cnt

    def deal_folder(self, group, folder_path, ele_index, topic_type, allowed_extensions):
        latest_database = {}
        datanames = os.listdir(folder_path)

        for f in datanames:
            key, ext = os.path.splitext(f)
            if ext in allowed_extensions:
                latest_database[key] = os.path.join(folder_path, f)

        cnt = len(latest_database)
        if cnt > 0:
            self.data_frame_list = sorted(latest_database.keys())
            self.offline_frame_cnt = cnt
            send_log_msg(NORMAL, f"共发现了{'、'.join(allowed_extensions)}格式的文件 {cnt} 帧")

            group_data = self.database.setdefault(group, {})
            topic_data = group_data.setdefault(topic_type, [])

            if ele_index < len(topic_data):
                topic_data[ele_index] = latest_database
            else:
                topic_data.append(latest_database)

        return cnt
