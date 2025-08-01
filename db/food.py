import os
import sqlite3
import db
import db.session
import src.utils as utils
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

def delete_food(sid: str, fid: str) -> utils.ResultDTO:
    session_info = db.session.get_info(sid)
    if not session_info.result:
        return session_info
    
    uid = session_info.data['session_info']['uid']
    
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    # 식품 ID와 유저 ID가 일치하는 식품 정보 삭제
    cursor.execute("DELETE FROM foods WHERE fid = ? AND uid = ?", (fid, uid))
    conn.commit()
    
    if cursor.rowcount == 0:
        db.close_db_connection(conn)
        return utils.ResultDTO(code=404, message="등록된 식품 정보를 찾을 수 없습니다.", result=False)
    
    db.close_db_connection(conn)
    return utils.ResultDTO(code=200, message="성공적으로 삭제되었습니다.", result=True)

def get_info(sid: str, fid: str) -> utils.ResultDTO:
    session_info = db.session.get_info(sid)
    if not session_info.result:
        return session_info

    if not fid:
        return utils.ResultDTO(code=400, message="유효하지 않은 식품 ID입니다.", result=False)
    
    conn = db.get_db_connection()
    cursor = conn.cursor()

    # 유저 ID와 식품 ID가 일치하는 식품 정보 조회
    uid = session_info.data['session_info']['uid']
    cursor.execute("SELECT * FROM foods WHERE fid = ? AND uid = ?", (fid, uid))
    row = cursor.fetchone()
    
    if not row:
        db.close_db_connection(conn)
        return utils.ResultDTO(code=404, message="등록된 식품 정보를 찾을 수 없습니다.", result=False)
    row = dict(row)
    
    db.close_db_connection(conn)
    return utils.ResultDTO(code=200, message="성공적으로 조회되었습니다.", data={'food_info': row}, result=True)

def get_list_info(sid: str) -> utils.ResultDTO:
    session_info = db.session.get_info(sid)
    # 잘못된 세션 ID일 경우 실패 처리
    if not session_info.result:
        return session_info
    
    uid = session_info.data['session_info']['uid']
    
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM foods WHERE uid = ?", (uid,))
    rows = cursor.fetchall()
    
    if not rows:
        db.close_db_connection(conn)
        return utils.ResultDTO(code=404, message="등록된 식품 정보가 없습니다.", result=False)
    
    food_list = [dict(row) for row in rows]
    
    db.close_db_connection(conn)
    return utils.ResultDTO(code=200, message="성공적으로 조회되었습니다.", data={'food_list': food_list}, result=True)

def regi_food_with_barcode(sid:str, barcode:str, food_count:int) -> utils.ResultDTO:
    session_info = db.session.get_info(sid)
    # 잘못된 세션 ID일 경우 실패 처리
    if not session_info.result:
        return session_info
    
    # 잘못된 바코드 값일 경우 실패 처리
    if not barcode or not utils.is_valid_barcode(barcode):
        return utils.ResultDTO(code=400, message="유효하지 않은 바코드 형식입니다. (12~13자리 숫자)", result=False)
    
    # 잘못된 식품 수량일 경우 실패 처리
    if food_count <= 0 or food_count > 100:
        return utils.ResultDTO(code=400, message="식품 수량은 1 이상 100 이하이어야 합니다.", result=False)
    
    # 식품의 이름, 종류(유탕면, 음료 등), 유통기한 가져오기
    food_name = None
    food_type = None
    food_expiration_date = None
    food_expiration_date_desc = None
    food_image_url = None
    food_volume = None
    try:
        # get Food name, type, expiration date
        foodsafety_api_url = f"http://openapi.foodsafetykorea.go.kr/api/{os.environ['FOODSAFETYKOREA_API_KEY']}/C005/json/1/100/BAR_CD={barcode}"
        response = requests.get(foodsafety_api_url)
        response_json = response.json()
        row = response_json['C005']['row'][0]
        food_name = row['PRDLST_NM']
        food_type = row['PRDLST_DCNM']
        food_expiration_date = datetime.now() + timedelta(days=utils.extract_months(row['POG_DAYCNT'])*30)
        food_expiration_date_desc = row['POG_DAYCNT']
        
        retaildb_api_url = f"https://www.retaildb.or.kr/service/product_info/search/{barcode}"
        response = requests.get(retaildb_api_url, verify=False)
        response_json = response.json()
        food_volume = response_json['originVolume']
        food_image_url = response_json['images'][0]
    except:
        pass
    
    # DB 작성
    fid = utils.gen_hash(16)
    uid = session_info.data['session_info']['uid']
    conn = db.get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO foods (fid, uid, name, type, description, count, volume, image_url, barcode, expiration_date_desc, expiration_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (fid, uid, food_name, food_type, food_name, food_count, food_volume, food_image_url, barcode, food_expiration_date_desc, utils.datetime_to_str(food_expiration_date)))
        conn.commit()
        db.close_db_connection(conn)
    except:
        db.close_db_connection(conn)
        return utils.ResultDTO(code=409, message="등록 중 오류가 발생했습니다.", result=False)

    return utils.ResultDTO(code=200, message="등록 성공", data=get_info(sid, fid).data, result=True)