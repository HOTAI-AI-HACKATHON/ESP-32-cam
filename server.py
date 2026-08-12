from flask import Flask, request
import os
from datetime import datetime
import cv2
import numpy as np
import shutil

app = Flask(__name__)

# 建立所需資料夾
os.makedirs("pre_image", exist_ok=True)
os.makedirs("after_image", exist_ok=True)
os.makedirs("history", exist_ok=True)
os.makedirs("results", exist_ok=True)

def read_image_utf8(path):
    with open(path, "rb") as f:
        return cv2.imdecode(np.frombuffer(f.read(), dtype=np.uint8), cv2.IMREAD_COLOR)

def process_image(pre_image_path, after_image_path):
    img_template = read_image_utf8(pre_image_path)
    img_test = read_image_utf8(after_image_path)
    
    if img_template is None or img_test is None:
        return "讀取圖片失敗"

    gray_temp = cv2.cvtColor(img_template, cv2.COLOR_BGR2GRAY)
    gray_test = cv2.cvtColor(img_test, cv2.COLOR_BGR2GRAY)

    orb = cv2.ORB_create(nfeatures=3000)
    kp_temp, des_temp = orb.detectAndCompute(gray_temp, None)
    kp_test, des_test = orb.detectAndCompute(gray_test, None)

    if des_temp is None or des_test is None:
        return "無法取得特徵點"

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des_temp, des_test)
    matches = sorted(matches, key=lambda x: x.distance)

    if len(matches) > 10:
        pts_temp = np.float32([kp_temp[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        pts_test = np.float32([kp_test[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

        M, inliers_mask = cv2.findHomography(pts_test, pts_temp, cv2.RANSAC, 5.0)
        
        if M is None:
            return "無法對齊圖片"

        # 準備畫特徵連線圖供展示
        inliers_matches = [matches[i] for i in range(len(matches)) if inliers_mask[i][0] == 1]
        img_clean_matches = cv2.drawMatches(img_template, kp_temp, img_test, kp_test, inliers_matches[:50], None, flags=2)

        h, w, c = img_template.shape
        img_test_aligned = cv2.warpPerspective(img_test, M, (w, h))

        gray_aligned = cv2.cvtColor(img_test_aligned, cv2.COLOR_BGR2GRAY)

        gray_temp_norm = cv2.normalize(gray_temp, None, 0, 255, cv2.NORM_MINMAX)
        gray_aligned_norm = cv2.normalize(gray_aligned, None, 0, 255, cv2.NORM_MINMAX)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_temp_enhanced = clahe.apply(gray_temp_norm)
        gray_aligned_enhanced = clahe.apply(gray_aligned_norm)

        gray_temp_blur = cv2.GaussianBlur(gray_temp_enhanced, (5, 5), 0)
        gray_aligned_blur = cv2.GaussianBlur(gray_aligned_enhanced, (5, 5), 0)

        img_diff = cv2.absdiff(gray_temp_blur, gray_aligned_blur)
        
        _, img_thresh = cv2.threshold(img_diff, 80, 255, cv2.THRESH_BINARY)
        
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
        img_closed = cv2.morphologyEx(img_thresh, cv2.MORPH_CLOSE, kernel_close)
        
        kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        img_cleaned_diff = cv2.morphologyEx(img_closed, cv2.MORPH_OPEN, kernel_open)

        # 儲存黑白差異圖
        res_diff_path = os.path.join("results", f"diff_{os.path.basename(after_image_path)}")
        cv2.imwrite(res_diff_path, img_cleaned_diff)
        
        # 儲存特徵點連線圖
        res_matches_path = os.path.join("results", f"matches_{os.path.basename(after_image_path)}")
        cv2.imwrite(res_matches_path, img_clean_matches)

        # 彈出視窗展示 (3秒後自動關閉)
        cv2.namedWindow("1. Feature Matches", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("1. Feature Matches", 800, 450)
        cv2.imshow("1. Feature Matches", img_clean_matches)

        cv2.namedWindow("2. Detected Anomalies", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("2. Detected Anomalies", 600, 450)
        cv2.imshow("2. Detected Anomalies", img_cleaned_diff)
        
        cv2.waitKey(3000)
        cv2.destroyAllWindows()

        white_pixels = cv2.countNonZero(img_cleaned_diff)
        total_pixels = img_cleaned_diff.size
        anomaly_ratio = (white_pixels / total_pixels) * 100

        if anomaly_ratio > 0.5:
            return f"發現新車損或髒污(差異: {anomaly_ratio:.2f}%)"
        else:
            return f"車況正常 (差異: {anomaly_ratio:.2f}%)"
    else:
        return "圖片配對失敗：可能是拍錯位置或模糊"

@app.route('/upload', methods=['POST'])
def upload_image():
    if request.data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        
        # 取得 pre_image 資料夾內的檔案列表
        pre_files = os.listdir("pre_image")
        
        if len(pre_files) == 0:
            # 第一輪: 借車
            filename = f"pre_image/before_{timestamp}.jpg"
            with open(filename, "wb") as f:
                f.write(request.data)
            print(f"\n--- [借車] 收到第一張基準照片: {filename} ---")
            return "借車前狀態已記錄", 200
            
        else:
            # 第二輪: 還車
            filename = f"after_image/after_{timestamp}.jpg"
            with open(filename, "wb") as f:
                f.write(request.data)
            print(f"\n--- [還車] 收到第二張測試照片: {filename} ---")
            
            pre_img_path = os.path.join("pre_image", pre_files[0])
            print("正在比對前後車況...")
            result_msg = process_image(pre_img_path, filename)
            print(f"判讀結果: {result_msg}")
            
            # 歸檔，清空資料夾，準備下一次借車
            shutil.move(pre_img_path, f"history/before_{timestamp}.jpg")
            shutil.move(filename, f"history/after_{timestamp}.jpg")
            
            return result_msg, 200
            
    return "No Data", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)