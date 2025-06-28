import streamlit as st
from collections import Counter
import random
import math
import io
import pandas as pd
from datetime import datetime

# --- 乱数生成アルゴリズム定義 ---
class Xorshift:
    def __init__(self, seed):
        self.state = seed if seed != 0 else 1
    def next(self):
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17)
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x & 0xFFFFFFFF
        return self.state
    def generate(self, count):
        return [self.next() for _ in range(count)]

def mersenne_twister(seed, count):
    random.seed(seed)
    return [random.randint(0, 100000) for _ in range(count)]

def middle_square(seed, count):
    n_digits = len(str(seed))
    value = seed
    result = []
    for _ in range(count):
        squared = value ** 2
        squared_str = str(squared).zfill(2 * n_digits)
        start = (len(squared_str) - n_digits) // 2
        middle_digits = int(squared_str[start:start + n_digits])
        result.append(middle_digits)
        value = middle_digits if middle_digits != 0 else seed + 1
    return result

def lcg(seed, count):
    m = 2**32; a = 1664525; c = 1013904223
    result = []; x = seed
    for _ in range(count):
        x = (a * x + c) % m
        result.append(x)
    return result

def calculate_variance(numbers, n):
    mod = [x % n for x in numbers]
    counts = Counter(mod)
    all_counts = [counts.get(i,0) for i in range(n)]
    expected = len(numbers)/n
    variance = sum((c-expected)**2 for c in all_counts)/n
    return variance, mod

@st.cache_data(show_spinner=False)
def find_best_seed_and_method(k, l, n):
    seed_range = range(0, 1000001, 100)
    count = k * l
    best = (float('inf'), None, None, None)
    for method in ["Xorshift","Mersenne Twister","Middle Square","LCG"]:
        for seed in seed_range:
            nums = {
                "Xorshift": Xorshift(seed).generate(count),
                "Mersenne Twister": mersenne_twister(seed,count),
                "Middle Square": middle_square(seed,count),
                "LCG": lcg(seed,count)
            }[method]
            var, modded = calculate_variance(nums, n)
            if var < best[0]:
                best=(var,method,seed,modded)
    return best[1],best[2],best[0],best[3]

def run_app():
    st.title("🎲 指名アプリ")

    # クラス選択と追加
    if "class_list" not in st.session_state:
        st.session_state.class_list = ["クラスA", "クラスB", "クラスC"]
    class_options = st.session_state.class_list
    new_class = st.text_input("➕ 新しいクラス名を追加", "")
    if st.button("追加") and new_class and new_class not in class_options:
        class_options.append(new_class)
    tab = st.sidebar.selectbox("クラス選択", class_options)

    st.header(f"📋 {tab} の設定")
    k = st.number_input("年間授業回数", value=30, min_value=1, key=tab+"k")
    l = st.number_input("授業1回あたりの平均指名人数", value=5, min_value=1, key=tab+"l")
    n = st.number_input("クラス人数", value=40, min_value=1, key=tab+"n")

    name_input = st.text_area("名前を改行区切りで入力（足りない分は自動補完します）", height=120, key=tab+"names")
    raw = [x.strip() for x in name_input.split("\n") if x.strip()]
    if len(raw)<n: raw += [f"名前{i+1}" for i in range(len(raw),n)]
    elif len(raw)>n: raw=raw[:n]
    names = raw
    st.write("👥 メンバー:", [f"{i+1} : {name}" for i,name in enumerate(names)])

    if st.button("📊 指名する準備を整える！", key=tab+"gen"):
        with st.spinner("⚙️ 指名する準備を整えています…"):
            method, seed, var, pool = find_best_seed_and_method(k, l, len(names))
            std = math.sqrt(var)
            exp = (k * l) / len(names)
            lb, ub = exp - std, exp + std
            st.session_state[tab + "_pool"] = pool
            st.session_state[tab + "_used"] = []
            st.session_state[tab + "_names"] = names

        st.success(f"✅ 使用した式: {method}（seed={seed}, 指名回数の偏り具合={std:.2f}）")
        st.markdown(
            f"""
            <div style="font-size: 28px; font-weight: bold; text-align: center; color: #2196F3; margin-top: 20px;">
                1人あたりの指名回数は 約 {lb:.2f} ～ {ub:.2f} 回です。
            </div>
            """,
            unsafe_allow_html=True
        )

    if st.button("🔄 全リセット", key=tab+"reset"):
        for key in [tab+"_pool",tab+"_used",tab+"_names"]:
            st.session_state.pop(key,None)
        st.experimental_rerun()

    # 📂 履歴読み込み（任意）
    st.markdown("📂 過去の履歴ファイルを読み込む（再開したいときに使ってね）")
    uploaded = st.file_uploader("CSVファイルを選択", type="csv", key=tab+"upload")
    if uploaded:
        df = pd.read_csv(uploaded)
        indices = [int(row["番号"])-1 for _, row in df.iterrows()]
        st.session_state[tab+"_used"] = indices
        st.success("📥 履歴を読み込みました！")

    # 🔊 音声ファイル（MP3）アップロード（任意）
    st.markdown("🔊 指名時に再生する音声をアップロード（MP3）")
    sound_file = st.file_uploader("音声ファイルを選んでね", type=["mp3"], key=tab+"mp3")

    # 🎯 指名セッション
    if (tab+"_pool" in st.session_state) and (tab+"_names" in st.session_state):
        pool = st.session_state[tab+"_pool"]
        used = st.session_state[tab+"_used"]
        names = st.session_state[tab+"_names"]
        pc, uc = Counter(pool), Counter(used)

        absent_input = st.text_area("⛔ 欠席者をここに入力（1回の指名ごとに変更可能）", height=80, key=tab+"absent_realtime")
        absents = [x.strip() for x in absent_input.split("\n") if x.strip()]
        available = [i for i, name in enumerate(names) if name not in absents]

        if st.button("🎯 指名！", key=tab+"pick"):
            rem = [i for i in (pc - uc).elements() if i in available]
            if rem:
                sel = random.choice(rem)
                st.session_state[tab+"_used"].append(sel)
                st.markdown(f"<div style='font-size:64px;text-align:center;color:#4CAF50;margin:30px;'>🎉 {sel+1} : {names[sel]} 🎉</div>", unsafe_allow_html=True)

                if sound_file:
                    st.audio(sound_file, format='audio/mp3')
            else:
                st.warning("✅ 全回数分の指名が完了しました！")

        used = st.session_state[tab+"_used"]
        df = pd.DataFrame([(i+1, names[i]) for i in used], columns=["番号", "名前"])
        csv = io.StringIO(); df.to_csv(csv, index=False)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"{tab}_{timestamp}_history.csv"
        st.download_button("⬇️ 指名履歴のダウンロード", csv.getvalue(), file_name=filename)

        rem = len(list((pc - Counter(used)).elements()))
        st.write(f"📌 残り指名可能人数: {rem} / {len(pool)}")

        if used:
            st.write("📋 指名済み:")
            st.write(df)

if __name__ == "__main__":
    run_app()


