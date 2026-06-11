"""
Generator: dim_district
Rows: ~700 (phân bổ thực tế: HCM 24, HN 30, tỉnh lớn 10-15, tỉnh nhỏ 5-8)
Output: data/raw/dim_district.parquet
Dependencies: dim_province
"""
from pathlib import Path
import numpy as np
import pandas as pd

# Số quận/huyện mỗi tỉnh — thực tế hành chính VN
DISTRICT_COUNT = {
    1:  30,   # Hà Nội
    2:  11,   # Hà Giang
    4:  13,   # Cao Bằng
    6:  8,    # Bắc Kạn
    8:  7,    # Tuyên Quang
    10: 9,    # Lào Cai
    11: 9,    # Điện Biên
    12: 8,    # Lai Châu
    14: 12,   # Sơn La
    15: 9,    # Yên Bái
    17: 11,   # Hoà Bình
    19: 9,    # Thái Nguyên
    20: 11,   # Lạng Sơn
    22: 13,   # Quảng Ninh
    24: 10,   # Bắc Giang
    25: 13,   # Phú Thọ
    26: 9,    # Vĩnh Phúc
    27: 8,    # Bắc Ninh
    30: 12,   # Hải Dương
    31: 15,   # Hải Phòng
    33: 10,   # Hưng Yên
    34: 8,    # Thái Bình
    35: 6,    # Hà Nam
    36: 10,   # Nam Định
    37: 8,    # Ninh Bình
    38: 27,   # Thanh Hóa
    40: 21,   # Nghệ An
    42: 13,   # Hà Tĩnh
    44: 8,    # Quảng Bình
    45: 10,   # Quảng Trị
    46: 9,    # Thừa Thiên Huế
    48: 8,    # Đà Nẵng
    49: 18,   # Quảng Nam
    51: 14,   # Quảng Ngãi
    52: 11,   # Bình Định
    54: 9,    # Phú Yên
    56: 9,    # Khánh Hòa
    58: 7,    # Ninh Thuận
    60: 10,   # Bình Thuận
    62: 10,   # Kon Tum
    64: 17,   # Gia Lai
    66: 15,   # Đắk Lắk
    67: 8,    # Đắk Nông
    68: 12,   # Lâm Đồng
    70: 11,   # Bình Phước
    72: 8,    # Bà Rịa - Vũng Tàu
    74: 9,    # Bình Dương
    75: 11,   # Đồng Nai
    77: 9,    # Tây Ninh
    79: 24,   # Hồ Chí Minh
    80: 15,   # Long An
    82: 11,   # Tiền Giang
    83: 9,    # Bến Tre
    84: 9,    # Trà Vinh
    86: 8,    # Vĩnh Long
    87: 12,   # Đồng Tháp
    89: 11,   # An Giang
    91: 15,   # Kiên Giang
    92: 9,    # Cần Thơ
    93: 8,    # Hậu Giang
    94: 11,   # Sóc Trăng
    95: 7,    # Bạc Liêu
    96: 9,    # Cà Mau
}

# Prefix tên quận/huyện theo loại đơn vị hành chính
_PREFIXES = ["Quận", "Huyện", "Thị xã", "Thành phố"]
_PREFIX_WEIGHTS = [0.25, 0.55, 0.12, 0.08]

# Tên hậu tố phổ biến để tạo tên thực tế hơn
_SUFFIXES = [
    "Bắc", "Nam", "Đông", "Tây", "Trung",
    "Long", "Phú", "Tân", "Hòa", "An",
    "Thịnh", "Phong", "Hải", "Sơn", "Giang",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
]


def generate(seed: int = 42, **kwargs) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    province_df = kwargs.get("province_df")
    if province_df is None:
        province_df = pd.read_parquet("data/raw/dim_province.parquet")

    prov_map = province_df.set_index("province_id")["province_name"].to_dict()

    rows = []
    district_id = 10_001   # bắt đầu từ 10001 để không conflict với province_id
    for province_id in sorted(DISTRICT_COUNT.keys()):
        n = DISTRICT_COUNT[province_id]
        province_name = prov_map[province_id]
        prefixes = rng.choice(_PREFIXES, size=n, p=_PREFIX_WEIGHTS)
        suffixes = rng.choice(_SUFFIXES, size=n, replace=False if n <= len(_SUFFIXES) else True)
        for i in range(n):
            rows.append({
                "district_id":   district_id,
                "district_name": f"{prefixes[i]} {suffixes[i]}",
                "province_id":   province_id,
                "province_name": province_name,
            })
            district_id += 1

    df = pd.DataFrame(rows)
    return df


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


if __name__ == "__main__":
    df = generate()
    out = Path("data/raw/dim_district.parquet")
    write(df, out)
    print(f"dim_district: {len(df)} rows → {out}")
