import datetime
import os
import time

import easyocr
import piexif
import pytesseract
from PIL import Image
import cv2
import ddddocr

DEFAULT_PIC_WIDTH = 2560  # 默认是2K分辨率
PIC_2560_CROP_BOX = tuple([16, 38, 349, 89])  # 2560 x 1440 的图片
MEDIA_FOLDER = './海马爸比'
TIME_FOLDER = './时间图片'
TESSERACT_PATH = r'/opt/homebrew/Cellar/tesseract/5.4.1_2/bin/tesseract'
TESSERACT_CONFIG = r'-c tessedit_char_whitelist=-0123456789 --psm 6'

easyocr_reader = easyocr.Reader(['en'])
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
dddd_ocr = ddddocr.DdddOcr()
dddd_ocr_beta = ddddocr.DdddOcr(beta=True)
# ------------------------------------------------------------------
## general functions
# ------------------------------------------------------------------

def set_media_time(media_path, media_date):
    """
    给照片、视频设置拍摄时间
    """
    success = False  # 两个步骤一个成功则为成功
    media_time = media_date.replace('-', ':') + " 12:00:00"  # 格式为'2024:09:01 12:00:00'
    # 修改EXIF信息
    try:
        exif_dict = piexif.load(media_path)  # 读取现有Exif信息
        # 设置Exif信息，注意DateTime在ImageIFD里面
        exif_dict['0th'][piexif.ImageIFD.DateTime] = media_time
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = media_time
        exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = media_time
        try:
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, media_path)  # 插入Exif信息
            success = True
        except Exception as e:
            if str.upper(media_path).endswith('.JPG') or str.upper(media_path).endswith('.JPEG'):
                print(f'  Exif dump 失败: {media_path} - {e}')
    except Exception as e:
        if str.upper(media_path).endswith('.JPG') or str.upper(media_path).endswith('.JPEG'):
            print(f'  Exif load 失败: {media_path} - {e}')
    # 修改文件的修改日期和访问日期
    try:
        mod_time = time.mktime(time.strptime(media_time, '%Y:%m:%d %H:%M:%S'))
        os.utime(media_path, (mod_time, mod_time))
        success = True
    except Exception as e:
        print(f'  修改文件时间失败: {media_path} - {e}')
    return success

def change_media_name(media_path, media_date, prefix):
    """
    修改名称
    """
    file_ext = os.path.splitext(media_path)[1]
    count = 1
    new_media_name = prefix + f'{media_date}' + file_ext
    while new_media_name in os.listdir(MEDIA_FOLDER):
        new_media_name = prefix +  f'{media_date}_{count}' + file_ext
        count += 1
    new_media_path = os.path.join(MEDIA_FOLDER, new_media_name)
    os.rename(media_path, new_media_path)

def crop_pic(pic_path):
    """
    裁剪图片，只需要带有时间的部分，提高识别准确率
    """
    # 如果临时文件夹不存在则新建
    if not os.path.exists(TIME_FOLDER):
        os.mkdir(TIME_FOLDER)
    new_pic_path = os.path.join(TIME_FOLDER, pic_path.split('/')[-1])
    pic_origin = Image.open(pic_path)
    pic_width = pic_origin.size[0]
    pic_crop_box = []
    if pic_width != DEFAULT_PIC_WIDTH:
        for coordinate in PIC_2560_CROP_BOX:
            pic_crop_box.append((pic_width / DEFAULT_PIC_WIDTH) * coordinate)
    else: pic_crop_box = PIC_2560_CROP_BOX
    pic_new = pic_origin.crop(pic_crop_box)
    pic_new.save(new_pic_path)
    return new_pic_path

def upgrade_pic_date(pic_date):
    pic_date = pic_date.strip().replace('-', '').replace('z', '2')
    pic_date = "".join(filter(str.isdigit, pic_date))
    return pic_date

def check_date_valid(pic_date):
    now_date_str = datetime.datetime.now().strftime('%Y-%m-%d')
    return datetime.datetime.strptime(now_date_str, "%Y-%m-%d") >= datetime.datetime.strptime(pic_date, '%Y-%m-%d') > datetime.datetime.strptime('2023-09-17', '%Y-%m-%d')

def ocr_haima_pic_to_string(pic_path):
    result_list = []
    # easyocr
    easyocr_result = easyocr_reader.readtext(pic_path, detail=0, allowlist='-0123456789')
    if len(easyocr_result) > 0:
        easy_pic_date = upgrade_pic_date(easyocr_result[0])
        try:
            easy_pic_date = datetime.datetime.strptime(easy_pic_date, "%Y%m%d").strftime('%Y-%m-%d')
            if check_date_valid(easy_pic_date):
                result_list.append(easy_pic_date)
            else:
                print("easyocr异常时间忽略: ", easy_pic_date)
        except ValueError:
            pass

    # tesseract
    tesseract_pic_date = pytesseract.image_to_string(Image.open(pic_path), config=TESSERACT_CONFIG, lang='eng')
    tesseract_pic_date = upgrade_pic_date(tesseract_pic_date)
    try:
        tesseract_pic_date = datetime.datetime.strptime(tesseract_pic_date, "%Y%m%d").strftime('%Y-%m-%d')
        if check_date_valid(tesseract_pic_date):
            result_list.append(tesseract_pic_date)
        else: print("tesseract异常时间忽略: ", tesseract_pic_date)
    except ValueError:
        pass

    # ddddocr
    image = open(pic_path, "rb").read()
    dddd_pic_date = upgrade_pic_date(dddd_ocr.classification(image))
    try:
        dddd_pic_date = datetime.datetime.strptime(dddd_pic_date, "%Y%m%d").strftime('%Y-%m-%d')
        if check_date_valid(dddd_pic_date):
            result_list.append(dddd_pic_date)
        else: print("ddddocr异常时间忽略: ", dddd_pic_date)
    except ValueError:
        pass

    # ddddocr beta
    dddd_beta_pic_date = upgrade_pic_date(dddd_ocr_beta.classification(image))
    try:
        dddd_beta_pic_date = datetime.datetime.strptime(dddd_beta_pic_date, "%Y%m%d").strftime('%Y-%m-%d')
        if check_date_valid(dddd_beta_pic_date):
            result_list.append(dddd_beta_pic_date)
        else: print("ddddocr beta异常时间忽略: ", dddd_beta_pic_date)
    except ValueError:
        pass

    if len(result_list) == 0: return ''

    # 把所有结果汇总按照少数服从多数决定
    result_set = set(result_list)
    if len(result_set) != len(result_list):
        result_dict = {}
        for i in result_set:
            result_dict[i] = result_list.count(i)
        result_list = sorted(result_dict.items(), key=lambda x: x[1], reverse=True)
        if len(result_list) == 1: print(f'照片识别信息：{result_list}')
        else: print(f'照片识别信息 - 少数服从多数：{result_list}')
        return result_list[0][0]
    else:
        print(f'照片识别信息 - 都一样就选择第一个：{result_list}')
        return result_list[0]

def deal_pics(pic_list):
    # 校验
    num_pics = len(pic_list)
    print(f'共有 {num_pics} 张图片需要处理')
    if len(pic_list) == 0: return
    index = 0
    for pic_name in pic_list:
        index+=1
        print(f'开始处理：{pic_name}（{index}/{num_pics}）......')
        pic_path = os.path.join(MEDIA_FOLDER, pic_name)  # 照片绝对路径
        orc_pic_path = crop_pic(pic_path)  # 裁剪只用于OCR识别
        pic_date = ocr_haima_pic_to_string(orc_pic_path)
        if len(pic_date) == 0:
            print('Sorry')
            continue
        if set_media_time(pic_path, pic_date) : change_media_name(pic_path, pic_date, 'IMG_HM_')
        print('Done')

def deal_videos(video_list):
    # 校验
    num_videos = len(video_list)
    print(f'共有 {num_videos} 个视频需要处理')
    if num_videos == 0: return
    index = 0
    # 取视频首帧并识别
    for video_name in video_list:
        index += 1
        print(f'开始处理：{video_name}（{index}/{num_videos}）......')
        video_path = os.path.join(MEDIA_FOLDER, video_name)
        save_temp_pic_path = os.path.join(TIME_FOLDER, video_name.split('.')[0] + '.jpg')
        # 打开视频文件
        cap = cv2.VideoCapture(video_path)
        # 获取第一帧
        ret, frame = cap.read()
        # 保存第一帧为图片
        cv2.imwrite(save_temp_pic_path, frame)
        # 释放资源
        cap.release()
        # 处理图片
        orc_pic_path = crop_pic(save_temp_pic_path)  # 裁剪只用于OCR识别
        video_date = ocr_haima_pic_to_string(orc_pic_path)
        if len(video_date) == 0:
            print('Sorry')
            continue
        if set_media_time(video_path, video_date): change_media_name(video_path, video_date, 'V_HM_')
        print('Done')

if __name__ == '__main__':
    # 做一些初始化工作
    if not os.path.exists(MEDIA_FOLDER):
        print("文件不存在，请在 海马爸比 文件夹中放入拍摄的图片和视频")
        os.mkdir(MEDIA_FOLDER)
        exit()
    os.makedirs(TIME_FOLDER, exist_ok=True)
    # 先获取指定文件夹下所有的文件
    files = os.listdir(MEDIA_FOLDER)
    # 过滤出所有的图片
    pics = []
    videos = []
    for file in files:
        # 已处理过的不再次处理
        file_extension = str.upper(os.path.splitext(file)[1][1:])
        if file_extension in ['JPG', 'JPEG', 'PNG']:
            if not file.startswith('IMG_HM_'): pics.append(file)
        if file_extension in ['MP4']:
            if not file.startswith('V_HM_'): videos.append(file)
    # 开始处理
    if len(pics) > 0: deal_pics(pics)
    if len(videos) > 0: deal_videos(videos)
