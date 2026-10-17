import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import io
import datetime

# ==========================================
# ページの設定
# ==========================================
st.set_page_config(
    page_title="komoEngConv2026-Part2",
    page_icon="🎧",
    layout="centered",
    initial_sidebar_state="expanded"
)

# --- APIキーの読み込み ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception as e:
    st.error("⚠️ Gemini APIキー（GEMINI_API_KEY）がStreamlitのSecretsに設定されていません。")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# --- セッション状態の初期化 ---
if "page" not in st.session_state:
    st.session_state.page = "step1"  # "step1", "step1_5", "step2", "step3", "step8", "motivation", "mypage"
if "raw_text" not in st.session_state:
    st.session_state.raw_text = ""
if "dialogs" not in st.session_state:
    st.session_state.dialogs = []  # [(speaker, text), ...]
if "step2_index" not in st.session_state:
    st.session_state.step2_index = 0
if "step3_index" not in st.session_state:
    st.session_state.step3_index = 0
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = []
if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False
if "quiz_score" not in st.session_state:
    st.session_state.quiz_score = 0
if "completed_today" not in st.session_state:
    st.session_state.completed_today = False
if "history" not in st.session_state:
    st.session_state.history = []  # 過去の履歴リスト
if "streak_count" not in st.session_state:
    st.session_state.streak_count = 1
if "last_study_date" not in st.session_state:
    st.session_state.last_study_date = ""

# --- ヘルパー関数: テキストからダイアログを抽出 ---
def parse_dialogs(text):
    lines = text.split('\n')
    parsed = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # **A:** などのパターンを想定
        if "**" in line:
            parsed.append(line)
    return parsed if parsed else [l for l in lines if l.strip()]

# --- サイドバー：ナビゲーション ---
with st.sidebar:
    st.title("🎧 後半アプリメニュー")
    if st.button("🏠 マイページ（履歴一覧）"):
        st.session_state.page = "mypage"
        st.rerun()
        
    st.markdown("---")
    st.markdown("### 📌 現在の進捗")
    current_page = st.session_state.page
    if current_page != "mypage":
        st.write(f"現在のモード: {current_page.upper()}")
    else:
        st.write("マイページ表示中")
        
    st.markdown("---")
    if st.button("🔄 最初からやり直す"):
        st.session_state.page = "step1"
        st.session_state.raw_text = ""
        st.session_state.dialogs = []
        st.session_state.step2_index = 0
        st.session_state.step3_index = 0
        st.session_state.quiz_submitted = False
        st.session_state.completed_today = False
        st.rerun()

# ==========================================
# メイン画面のルーティング
# ==========================================

# 【マイページ】
if st.session_state.page == "mypage":
    st.title("📚 マイページ（学習履歴）")
    st.write("これまでに学習したスクリプトの一覧です。クリックしていつでも再開できます。")
    
    if not st.session_state.history:
        st.info("まだ学習履歴がありません。STEP 1からスクリプトを読み込んで学習を始めましょう！")
    else:
        for idx, hist in enumerate(st.session_state.history):
            with st.container():
                st.markdown(f"**履歴 #{idx+1}** - 📅 {hist['date']}")
                st.text(hist['title'][:50] + "...")
                if st.button(f"📂 このスクリプトで学習を再開する #{idx+1}", key=f"load_hist_{idx}"):
                    st.session_state.raw_text = hist['text']
                    st.session_state.dialogs = parse_dialogs(hist['text'])
                    st.session_state.step2_index = 0
                    st.session_state.step3_index = 0
                    st.session_state.quiz_submitted = False
                    st.session_state.completed_today = False
                    st.session_state.page = "step1_5"
                    st.rerun()
                st.markdown("---")
                
    if st.button("⬅️ 学習画面に戻る"):
        st.session_state.page = "step1"
        st.rerun()

# 【STEP 1：テキストファイルの読み込み】
elif st.session_state.page == "step1":
    st.title("🗣️ ロールプレイ＆学習アプリ")
    st.subheader("STEP 1: テキストファイルの読み込み")
    st.write("前半アプリで作成したテキストファイルをアップロードするか、下のボックスに直接貼り付けてください。")
    
    uploaded_file = st.file_uploader("テキストファイルをアップロード (.txt)", type=["txt"])
    pasted_text = st.text_area("または、ここにテキストを直接貼り付け", height=150)
    
    target_text = ""
    if uploaded_file is not None:
        target_text = uploaded_file.getvalue().decode("utf-8")
    elif pasted_text:
        target_text = pasted_text
        
    if st.button("読み込みを完了して次へ進む"):
        if target_text.strip():
            st.session_state.raw_text = target_text
            st.session_state.dialogs = parse_dialogs(target_text)
            # 履歴に追加
            today_str = datetime.date.today().strftime("%Y-%m-%d %H:%M")
            st.session_state.history.append({
                "date": today_str,
                "title": target_text[:100],
                "text": target_text
            })
            st.session_state.page = "step1_5"
            st.rerun()
        else:
            st.warning("⚠️ テキストファイルがアップロードされていないか、中身が空です。")

# 【STEP 1.5：スクリプト表示と音声読み上げ】
elif st.session_state.page == "step1_5":
    st.subheader("STEP 1.5: スクリプト確認と音声読み上げ")
    st.write("読み込んだスクリプトです。話者名を除いたセリフ部分を音声で確認できます。")
    
    st.markdown("### 📄 読み込み結果")
    st.text_area("スクリプト全体", st.session_state.raw_text, height=200, disabled=True)
    
    if st.button("🔊 ダイアログ全体を音声読み上げする"):
        # 話者名（**等）を除去してgTTSで読み上げ
        pure_text_lines = []
        for line in st.session_state.dialogs:
            cleaned = line.replace("**", "").replace("*", "")
            if ":" in cleaned:
                cleaned = cleaned.split(":", 1)[1]
            pure_text_lines.append(cleaned.strip())
        
        full_speech_text = " ".join(pure_text_lines)
        if full_speech_text:
            tts = gTTS(text=full_speech_text, lang='en')
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            st.audio(fp, format='audio/mp3')
            
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➡️ ロールプレイ前半 (STEP 2) へ進む"):
            st.session_state.page = "step2"
            st.session_state.step2_index = 0
            st.rerun()
    with col2:
        if st.button("⏭️ ロールプレイをスキップしてクイズ (STEP 8) へ"):
            st.session_state.page = "step8"
            st.rerun()

# 【STEP 2：ロールプレイ前半（AI先攻・ユーザー後攻）】
elif st.session_state.page == "step2":
    st.subheader("STEP 2: ロールプレイ前半（AI先攻・あなた後攻）")
    st.write("AIが最初の発話を行います。あなたのパートは画面を見ながら声に出して練習してください。")
    
    dialogs = st.session_state.dialogs
    idx = st.session_state.step2_index
    
    if dialogs and idx < len(dialogs):
        current_line = dialogs[idx]
        st.info(f"AIの発話ターン (第 {idx+1} / {len(dialogs)} 行)")
        st.markdown(f"**AI:** {current_line}")
        
        # 音声自動生成・再生
        cleaned_speech = current_line.replace("**", "").replace("*", "")
        if ":" in cleaned_speech:
            cleaned_speech = cleaned_speech.split(":", 1)[1]
        tts = gTTS(text=cleaned_speech.strip(), lang='en')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        st.audio(fp, format='audio/mp3', autoplay=True)
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if idx > 0 and st.button("◀️ ひとつ前に戻る"):
                st.session_state.step2_index -= 1
                st.rerun()
        with col2:
            if idx < len(dialogs) - 1:
                if st.button("次に進む ▶️"):
                    st.session_state.step2_index += 1
                    st.rerun()
            else:
                if st.button("🎉 STEP 2 完了！次のステップへ"):
                    st.session_state.page = "step3"
                    st.session_state.step3_index = 0
                    st.rerun()
    else:
        st.write("ダイアログが見つかりません。")
        if st.button("次へ進む"):
            st.session_state.page = "step3"
            st.rerun()

    st.markdown("---")
    if st.button("⏩ STEP 2をすべてとばす（STEP 3へ）"):
        st.session_state.page = "step3"
        st.session_state.step3_index = 0
        st.rerun()

# 【STEP 3：ロールプレイ後半（ユーザー先攻・AI後攻）】
elif st.session_state.page == "step3":
    st.subheader("STEP 3: ロールプレイ後半（あなた先攻・AI後攻）")
    st.write("あなたが先頭の発話を行い、AIが返事を行います。")
    
    dialogs = st.session_state.dialogs
    idx = st.session_state.step3_index
    
    if dialogs and idx < len(dialogs):
        current_line = dialogs[idx]
        st.info(f"あなたの発話ターン (第 {idx+1} / {len(dialogs)} 行)")
        st.markdown(f"**あなた:** {current_line} (声に出して読んでみましょう)")
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if idx > 0 and st.button("◀️ ひとつ前に戻る", key="back3"):
                st.session_state.step3_index -= 1
                st.rerun()
        with col2:
            if idx < len(dialogs) - 1:
                if st.button("次に進む ▶️", key="next3"):
                    st.session_state.step3_index += 1
                    st.rerun()
            else:
                if st.button("🎉 STEP 3 完了！理解度クイズへ"):
                    st.session_state.page = "step8"
                    st.rerun()
    else:
        st.write("ダイアログが見つかりません。")
        if st.button("次へ進む"):
            st.session_state.page = "step8"
            st.rerun()

    st.markdown("---")
    if st.button("⏩ STEP 3をすべてとばす（クイズへ）"):
        st.session_state.page = "step8"
        st.rerun()

# 【STEP 8：自動クイズ】
elif st.session_state.page == "step8":
    st.subheader("STEP 8: 理解度クイックチェック")
    st.write("スクリプトの内容に関する簡単な確認クイズです。")
    
    if not st.session_state.quiz_data:
        with st.spinner("AIがクイズを作成中..."):
            quiz_prompt = f"""以下の英語スクリプトから、重要表現に関する3択クイズを1問だけ作成してください。
JSON形式ではなく、以下の形式でプレーンテキストで出力してください。
QUESTION: [問題文]
CHOICES: [選択肢1, 選択肢2, 選択肢3]
ANSWER: [正解の選択肢]

スクリプト:
{st.session_state.raw_text}"""
            try:
                res = model.generate_content(quiz_prompt)
                st.session_state.quiz_data = res.text
            except Exception as e:
                st.session_state.quiz_data = "QUESTION: スクリプトの主要な目的は何ですか？\nCHOICES: 挨拶, 買い物, 日常会話\nANSWER: 買い物"
                
    st.text(st.session_state.quiz_data)
    user_choice = st.text_input("答えの選択肢を入力してください：")
    
    if not st.session_state.quiz_submitted:
        if st.button("解答を提出する"):
            if user_choice.strip():
                st.session_state.quiz_submitted = True
                st.session_state.completed_today = True  # すべて完了！
                st.rerun()
            else:
                st.warning("解答を入力してください。")
    else:
        st.success("解答を受け付けました！お疲れ様でした！")
        if st.button("✨ モチベーション結果を見る"):
            st.session_state.page = "motivation"
            st.rerun()

# 【モチベーション機能 ＆ 終了画面】
elif st.session_state.page == "motivation":
    st.title("🌟 本日の学習お疲れ様でした！")
    
    # スタンプ・連続日数のカウント処理
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    if st.session_state.last_study_date != today_str:
        st.session_state.streak_count += 1
        st.session_state.last_study_date = today_str
        
    # 画面表示
    st.markdown("### 🏆 学習スタンプ獲得！")
    st.success(f"ポンッ！ 🎯 本日の学習スタンプが押されました！")
    st.info(f"🔥 現在の連続学習日数: **{st.session_state.streak_count} 日目**")
    
    st.markdown("### 🤖 AIからの褒めメッセージ ＆ バッジ")
    st.markdown("> *「素晴らしい集中力でした！ロールプレイからクイズまで完璧にやり遂げましたね。今日培った英語表現はあなたの確実な力になっています！」*")
    st.markdown("🏅 **獲得バッジ:** 【完全燃焼チャレンジャー】")
    
    st.markdown("---")
    
    # マイページへ飛ぶボタン
    if st.button("📚 マイページ（履歴）を確認する"):
        st.session_state.page = "mypage"
        st.rerun()
        
    st.markdown("")
    
    # 今日の学習を終了して最初の画面に戻るボタン
    if st.button("🏠 今日の学習を終了して最初の画面に戻る"):
        st.session_state.page = "step1"
        st.session_state.completed_today = False
        st.session_state.quiz_submitted = False
        st.rerun()
