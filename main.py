# main.py (Gemini API version - 括弧チェック修正版)
import os
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .envファイルから環境変数を読み込む (任意)
load_dotenv()
logger.info(".envファイルを読み込みました (存在する場合)")

# --- Gemini APIキーの設定 ---
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    logger.error("環境変数 'GEMINI_API_KEY' が設定されていません。")
    raise ValueError("Gemini APIキーが環境変数に設定されていません。'GEMINI_API_KEY' を設定してください。")
try:
    genai.configure(api_key=gemini_api_key)
    logger.info("Gemini APIキーが正常に設定されました。")
except Exception as e:
    logger.error(f"Gemini APIキーの設定に失敗しました: {e}")
    exit()

# --- リクエスト/レスポンスモデルの定義 ---
class NameInput(BaseModel):
    name: str
class NameOutput(BaseModel):
    new_name: str

# --- FastAPIアプリケーションの初期化 ---
app = FastAPI(
    title="湯婆婆AI API (Gemini)",
    description="入力された名前を湯婆婆風の短い名前に変換するAPIです (Gemini版)。",
    version="1.1.1" # バージョンアップ
)

# --- CORS設定 ---
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORSミドルウェアを設定しました。許可オリジン: %s", origins)

# --- Geminiモデルの設定 ---
try:
    model = genai.GenerativeModel('gemini-1.5-flash')
    logger.info("Geminiモデル '%s' をロードしました。", 'gemini-1.5-flash')
except Exception as e:
    logger.error(f"Geminiモデルのロードに失敗しました: {e}")
    exit()


# --- 名前生成関数 (Gemini APIを使用 - 修正箇所) ---
def generate_yubaba_name_gemini(name: str) -> str:
    logger.info("名前生成関数が呼び出されました。入力名: %s", name)
    prompt = f"""あなたは銭婆の姉である湯婆婆です。贅沢な名前「{name}」を入力されたら、その名前から短く呼びやすい新しい名前を与えてください。新しい名前は、元の名前の漢字一文字（読みは元の名前に近いもの、または音読み）、または作中に登場する「千（セン）」や「ハク」のように非常に短い名前にしてください。新しい短い名前には読み仮名を（）で添えてください。

以下に名前変換の例を示します。

* 入力：山田太郎 → 出力：山（サン）
* 入力：佐藤花子 → 出力：花（ハナ）
* 入力：木村美咲 → 出力：咲（サキ）
* 入力：高橋健太 → 出力：橋（キョウ）
* 入力：渡辺優子 → 出力：優（ユウ）
* 入力：萩野千尋 → 出力：千（セン）
* 入力：伊藤さくら → 出力：藤（トウ）
* 入力：ニギハヤミコハクヌシ → 出力：ハク（ハク）

入力された名前に基づき、新しい短い名前（読み）のみを返してください。余計な前置きや説明は不要です。

入力：{name}
出力："""

    try:
        logger.info("Gemini APIにリクエストを送信します...")
        response = model.generate_content(prompt)
        logger.info("Gemini APIから応答を受信しました。")

        if response.parts:
             new_name = response.text.strip()
             logger.info("生成されたテキスト: %s", new_name)
             # ★★★ 括弧のチェックを修正 (全角括弧も許容) ★★★
             if ('(' in new_name and ')' in new_name) or \
                ('（' in new_name and '）' in new_name):
                 logger.info("期待した形式の名前を返します。")
                 return new_name
             else:
                 logger.warning("Geminiからの応答が期待した形式ではありませんでした: %s", new_name)
                 raise HTTPException(status_code=500, detail="名前の生成結果が予期せぬ形式です。")
        else:
            safety_ratings = response.prompt_feedback.safety_ratings if response.prompt_feedback else "N/A"
            logger.warning("Geminiからの応答にテキストパートが含まれませんでした。Safety Ratings: %s", safety_ratings)
            raise HTTPException(status_code=500, detail="名前の生成に失敗しました(応答なし)。")

    except Exception as e:
        logger.error("Gemini API呼び出しまたは処理中にエラーが発生しました: %s", e, exc_info=True)
        # HTTPException以外の予期せぬエラーの場合も500エラーを返す
        if not isinstance(e, HTTPException):
             raise HTTPException(status_code=500, detail=f"名前の生成中にサーバーエラーが発生しました。")
        else:
             # 発生したHTTPExceptionをそのまま再raiseする
             raise e


# --- APIエンドポイントの定義 ---
@app.post("/api/generate-name", response_model=NameOutput)
async def create_new_name(name_input: NameInput):
    logger.info("エンドポイント /api/generate-name が呼び出されました。")
    original_name = name_input.name
    if not original_name:
        logger.warning("名前が空でリクエストされました。")
        raise HTTPException(status_code=400, detail="名前が入力されていません。")

    try:
        new_name = generate_yubaba_name_gemini(original_name)
        logger.info("名前生成成功。クライアントに応答を返します。")
        return NameOutput(new_name=new_name)
    except HTTPException as http_exc:
        logger.error("名前生成関数内でHTTPExceptionが発生しました: %s", http_exc.detail)
        raise http_exc
    except Exception as e:
        logger.error("エンドポイント処理中に予期せぬエラーが発生しました: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="サーバー内部でエラーが発生しました。")

# --- ルートエンドポイント (動作確認用) ---
@app.get("/")
async def read_root():
    logger.info("ルートエンドポイント / が呼び出されました。")
    return {"message": "湯婆婆AI API (Gemini) へようこそ！"}

# --- サーバーの実行 ---
if __name__ == "__main__":
    print("サーバーを起動するには、ターミナルで以下のコマンドを実行してください:")
    print("uvicorn main:app --reload --port 8000")
