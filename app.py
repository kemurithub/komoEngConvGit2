import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import io
import datetime
import calendar

# ==========================================
# ページの設定
# ==========================================
st.set_page_config(
    page_title="komoEngConv2026-Part2",
    page_icon="🗣️",
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
    st.session_state.page = "step1"  # "step1", "step1_5", "step2", "motivation", "mypage"
if "raw_text" not in st.session_state:
    st.session_state.raw_text = ""
if "dialogs" not in st.session_state:
    st.session_state.dialogs = []  # [{'speaker': 'Daichi', 'text': '...'}, ...]
if "speakers" not in st.session_state:
    st.session_state.speakers = []
if "user_role" not in st.session_state:
    st.session_state.user_role = ""
if "tips_text" not in st.session_state:
    st.session_state.tips_text = ""
if "history" not in st.session_state:
    st.session_state.history = []
if "streak_count" not in st.session_state:
    st.session_state.streak_count = 1
if "last_study_date" not in st.session_state:
    st.session_state.last_study_date = ""
if "studied_dates" not in st.session_state:
    st.session_state.studied_dates = set()

# --- ヘルパー関数: テキストから話者・セリフ・ポイント（Tips）を抽出 ---
def parse_text_content(text):
    target_section = text
    if "【英語完成スクリプト】" in text:
        parts = text.split("【英語完成スクリプト】")
        if len(parts) > 1:
            after_title = parts[1]
            if "【日本語訳" in after_title:
                target_section = after_title.split("【日本語訳")[0]
            elif "---" in after_title:
                target_section = after_title.split("---")[0]

    lines = target_section.split('\n')
    parsed_dialogs = []
    speakers_set = set()
    
    for line in lines:
        line = line.strip()
        if line.startswith("**") and ":" in line:
            parts = line.split(":", 1)
            speaker = parts[0].replace("**", "").replace("*", "").strip()
            dialog_text = parts[1].replace("**", "").replace("*", "").strip()
            parsed_dialogs.append({"speaker": speaker, "text": dialog_text})
            speakers_set.add(speaker)
            
    # 【ポイント】セクションの抽出
    extracted_tips = ""
    if "【ポイント】" in text:
        tips_parts = text.split("【ポイント】")
        if len(tips_parts) > 1:
            extracted_tips = tips_parts[1].strip()
            
    return parsed_dialogs, list(speakers_set), extracted_tips

# --- サイドバー：ナビゲーション ---
with st.sidebar:
    st.title("🗣️ 後半アプリメニュー")
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
        st.session_state.speakers = []
        st.session_state.user_role = ""
        st.session_state.tips_text = ""
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
                    d_list, s_list, t_text = parse_text_content(hist['text'])
                    st.session_state.dialogs = d_list
                    st.session_state.speakers = s_list
                    st.session_state.tips_text = t_text
                    if s_list:
                        st.session_state.user_role = s_list[1] if len(s_list) > 1 else s_list[0]
                    st.session_state.page = "step1_5"
                    st.rerun()
                st.markdown("---")
                
    if st.button("⬅️ 学習画面に戻る"):
        st.session_state.page = "step1"
        st.rerun()

# 【STEP 1：テキストファイルの読み込み】
elif st.session_state.page == "step1":
    st.title("🗣️ komoEngConvApp_2")
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
            d_list, s_list, t_text = parse_text_content(target_text)
            st.session_state.dialogs = d_list
            st.session_state.speakers = s_list
            st.session_state.tips_text = t_text
            if s_list:
                st.session_state.user_role = s_list[1] if len(s_list) > 1 else s_list[0]
            
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

# 【STEP 1.5：スクリプト確認と音声読み上げ】
elif st.session_state.page == "step1_5":
    st.subheader("STEP 1.5: スクリプト確認と音声読み上げ")
    st.write("読み込んだスクリプトです。話者名を除いたセリフ部分を音声で確認できます。")
    
    st.markdown("### 📄 抽出された英語スクリプト")
    
    display_lines = [f"**{d['speaker']}:** {d['text']}" for d in st.session_state.dialogs]
    extracted_dialog_text = "\n".join(display_lines)
    st.text_area("英語セリフ部分", extracted_dialog_text, height=200, disabled=True)
    
    if st.button("🔊 ダイアログ全体を音声読み上げする"):
        pure_text_lines = [d['text'].replace("**", "").replace("*", "") for d in st.session_state.dialogs]
        full_speech_text = " ".join(pure_text_lines)
        if full_speech_text:
            tts = gTTS(text=full_speech_text, lang='en')
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            st.audio(fp, format='audio/mp3')
            
    st.markdown("---")
    if st.button("➡️ ロールプレイ実践 (STEP 2) へ進む"):
        st.session_state.page = "step2"
        st.rerun()

# 【STEP 2：ロールプレイ実践】
elif st.session_state.page == "step2":
    st.subheader("STEP 2: ロールプレイ実践")
    st.write("スクリプト全体を見ながら、自分の役のセリフは声に出して練習し、AIの役のセリフは音声ボタンで聞いて確認しましょう。両方の役柄で練習してみてください。")
    
    dialogs = st.session_state.dialogs
    speakers = st.session_state.speakers
    
    if speakers:
        default_idx = 0
        if st.session_state.user_role in speakers:
            default_idx = speakers.index(st.session_state.user_role)
            
        def role_changed():
            st.session_state.user_role = st.session_state.role_selectbox
            
        selected_role = st.selectbox(
            "あなたの役を選んでください：", 
            speakers, 
            index=default_idx, 
            key="role_selectbox",
            on_change=role_changed
        )
        if not st.session_state.user_role:
            st.session_state.user_role = selected_role
    
    st.markdown("---")
    
    for idx, d in enumerate(dialogs):
        is_user_turn = (d["speaker"] == st.session_state.user_role)
        
        if is_user_turn:
            st.info(f"👤 **{d['speaker']} (あなた):** {d['text']}  \n👉 *声に出して練習しましょう！*")
        else:
            st.warning(f"🤖 **{d['speaker']} (AI):** {d['text']}")
            if st.button(f"🔊 {d['speaker']} のセリフを聴く (行 {idx+1})", key=f"audio_{idx}"):
                clean_speech_text = d['text'].replace("**", "").replace("*", "")
                tts = gTTS(text=clean_speech_text, lang='en')
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)
                st.audio(fp, format='audio/mp3', autoplay=True)
        st.markdown("")

    st.markdown("---")
    
    # 役柄交代ボタン
    if len(speakers) >= 2:
        other_role = speakers[1] if st.session_state.user_role == speakers[0] else speakers[0]
        if st.button(f"🔄 役柄を交代する（次は「{other_role}」役で練習する）"):
            st.session_state.user_role = other_role
            st.rerun()

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ スクリプト確認に戻る"):
            st.session_state.page = "step1_5"
            st.rerun()
    with col2:
        if st.button("🎉 ロールプレイ完了！結果を見る"):
            st.session_state.page = "motivation"
            st.rerun()

# 【モチベーション機能 ＆ カレンダー風スタンプ ＆ 終了画面】
elif st.session_state.page == "motivation":
    st.title("🌟 本日の学習お疲れ様でした！")
    
    # スタンプ・連続日数のカウント処理
    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")
    
    if st.session_state.last_study_date != today_str:
        st.session_state.streak_count += 1
        st.session_state.last_study_date = today_str
        
    st.session_state.studied_dates.add(today_str)
        
    # 画面表示
    st.markdown("### 🏆 学習スタンプ獲得！")
    st.success(f"ポンッ！ 🎯 本日の学習スタンプが押されました！")
    st.info(f"🔥 現在の連続学習日数: **{st.session_state.streak_count} 日目**")
    
    # カレンダービューの表示（当月）
    st.markdown("### 📅 学習カレンダー（スタンプ帳）")
    year = today.year
    month = today.month
    
    cal = calendar.monthcalendar(year, month)
    month_name = today.strftime("%Y年 %B")
    
    st.markdown(f"**{month_name}**")
    
    cols = st.columns(7)
    days_of_week = ["月", "火", "水", "木", "金", "土", "日"]
    for i, day_name in enumerate(days_of_week):
        cols[i].markdown(f"<div style='text-align: center;'><b>{day_name}</b></div>", unsafe_allow_html=True)
        
    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].markdown("<div style='text-align: center; color: #ccc;'>-</div>", unsafe_allow_html=True)
            else:
                date_obj = datetime.date(year, month, day)
                date_str = date_obj.strftime("%Y-%m-%d")
                if date_str in st.session_state.studied_dates:
                    cols[i].markdown(f"<div style='text-align: center; background-color: #d4edda; border-radius: 5px; padding: 4px;'><b>{day}</b><br>⭐</div>", unsafe_allow_html=True)
                else:
                    cols[i].markdown(f"<div style='text-align: center; padding: 4px;'>{day}</div>", unsafe_allow_html=True)
                    
    st.markdown("---")
    
    # 💡 学習のポイント（Tips）の表示
    st.markdown("### 💡 本日の学習のポイント ＆ Tips")
    if st.session_state.tips_text:
        st.markdown(st.session_state.tips_text)
    else:
        st.info("今日のスクリプトに関する特別なポイントはありません。たくさん声に出して練習したことが最高の財産です！")
        
    st.markdown("---")
    
    # 🤖 Tipsをふまえた自然な褒めメッセージ
    st.markdown("### 🤖 本日の振り返りコメント")
    tips_summary = st.session_state.tips_text if st.session_state.tips_text else "自然な表現"
    st.markdown(f"> *「両方の役柄でしっかり声に出して練習できましたね！今回のポイント（{tips_summary[:40]}...等）を意識しながら会話のキャッチーなニュアンスを掴めたのは素晴らしいアプローチです。この調子で自分の言葉として定着させていきましょう！」*")
    
    st.markdown("---")
    
    # マイページへ飛ぶボタン
    if st.button("📚 マイページ（履歴）を確認する"):
        st.session_state.page = "mypage"
        st.rerun()
        
    st.markdown("")
    
    # 今日の学習を終了して最初の画面に戻るボタン
    if st.button("🏠 今日の学習を終了して最初の画面に戻る"):
        st.session_state.page = "step1"
        st.rerun()
