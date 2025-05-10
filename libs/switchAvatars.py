import cv2
import numpy as np
import requests
import os
import tempfile
from libs.basic import *

def download_image(url, timeout=5):
    """下载图片到临时文件"""
    try:
        response = requests.get(url, stream=True, timeout=timeout)
        if response.status_code == 200:
            # 创建临时文件
            fd, path = tempfile.mkstemp(suffix='.jpg')
            with os.fdopen(fd, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return path
        return None
    except Exception as e:
        _log.error(f"下载失败: {str(e)}")
        return None

def compare_qq_avatars(qq_number, openid):
    """
    返回值说明: (相似度, 错误代码, 错误信息)
    错误代码定义:
    0 - 成功
    1 - QQ头像下载失败
    2 - OpenID头像下载失败
    3 - 图片尺寸不符
    4 - 图片读取失败
    5 - 直方图计算失败
    """
    qq_url = f"https://q.qlogo.cn/g?b=qq&nk={qq_number}&s=100"
    openid_url = getQLogoUrl(OpenID=openid, size=100)

    # 下载图片并捕获具体错误
    path1 = download_image(qq_url)
    if not path1:
        return (-1.0, 1, f"QQ头像下载失败（可能原因：网络超时/QQ号不存在） URL: {qq_url}")

    path2 = download_image(openid_url)
    if not path2:
        os.remove(path1)  # 清理已下载的QQ头像
        return (-1.0, 2, f"OpenID头像下载失败（可能原因：授权过期/用户未设置） URL: {openid_url}")

    try:
        # 读取图片
        img1 = cv2.imread(path1, cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imread(path2, cv2.IMREAD_GRAYSCALE)

        # 校验图片有效性
        if img1 is None or img2 is None:
            error_type = 4
            error_msg = "图片读取失败（可能原因：文件损坏/无效格式）"
            if img1 is None: error_msg += f" | QQ头像路径: {path1}"
            if img2 is None: error_msg += f" | OpenID头像路径: {path2}"
            return (-1.0, error_type, error_msg)

        # 校验图片尺寸
        if img1.shape != (100, 100) or img2.shape != (100, 100):
            error_size = f"QQ头像尺寸: {img1.shape if img1 is not None else '无效'}, " \
                        f"OpenID头像尺寸: {img2.shape if img2 is not None else '无效'}"
            return (-1.0, 3, f"图片尺寸不符（要求100x100）{error_size}")

        # 计算直方图
        try:
            hist1 = cv2.calcHist([img1], [0], None, [16], [0, 256])
            hist2 = cv2.calcHist([img2], [0], None, [16], [0, 256])
        except cv2.error as e:
            return (-1.0, 5, f"直方图计算失败（OpenCV错误：{str(e)}）")

        # 计算相似度
        similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        return (max(0.0, similarity), 0, "成功")

    finally:
        # 确保清理文件
        for p in [path1, path2]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception as e:
                    _log.error(f"文件清理失败: {str(e)}")

# 使用示例
if __name__ == "__main__":
    result = compare_qq_avatars("123456", "ABCD")
    if result[1] == 0:
        print(f"相似度：{result[0]:.2%}")
    else:
        print(f"错误 ({result[1]}): {result[2]}")

