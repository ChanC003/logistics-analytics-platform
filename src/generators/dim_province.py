"""
Generator: dim_province
Rows: 63 (hardcode — 63 tỉnh/thành VN chuẩn hành chính)
Output: data/raw/dim_province.parquet
Dependencies: none
"""
from pathlib import Path
import pandas as pd

# 63 tỉnh/thành — province_id theo chuẩn GHN OpenMetadata
# region_idx: 0=Miền Bắc  1=Miền Trung  2=Tây Nguyên  3=Miền Nam
PROVINCES = [
    (1,  "Hà Nội",              "Miền Bắc",   0),
    (2,  "Hà Giang",            "Miền Bắc",   0),
    (4,  "Cao Bằng",            "Miền Bắc",   0),
    (6,  "Bắc Kạn",             "Miền Bắc",   0),
    (8,  "Tuyên Quang",         "Miền Bắc",   0),
    (10, "Lào Cai",             "Miền Bắc",   0),
    (11, "Điện Biên",           "Miền Bắc",   0),
    (12, "Lai Châu",            "Miền Bắc",   0),
    (14, "Sơn La",              "Miền Bắc",   0),
    (15, "Yên Bái",             "Miền Bắc",   0),
    (17, "Hoà Bình",            "Miền Bắc",   0),
    (19, "Thái Nguyên",         "Miền Bắc",   0),
    (20, "Lạng Sơn",            "Miền Bắc",   0),
    (22, "Quảng Ninh",          "Miền Bắc",   0),
    (24, "Bắc Giang",           "Miền Bắc",   0),
    (25, "Phú Thọ",             "Miền Bắc",   0),
    (26, "Vĩnh Phúc",           "Miền Bắc",   0),
    (27, "Bắc Ninh",            "Miền Bắc",   0),
    (30, "Hải Dương",           "Miền Bắc",   0),
    (31, "Hải Phòng",           "Miền Bắc",   0),
    (33, "Hưng Yên",            "Miền Bắc",   0),
    (34, "Thái Bình",           "Miền Bắc",   0),
    (35, "Hà Nam",              "Miền Bắc",   0),
    (36, "Nam Định",            "Miền Bắc",   0),
    (37, "Ninh Bình",           "Miền Bắc",   0),
    (38, "Thanh Hóa",           "Miền Trung", 1),
    (40, "Nghệ An",             "Miền Trung", 1),
    (42, "Hà Tĩnh",             "Miền Trung", 1),
    (44, "Quảng Bình",          "Miền Trung", 1),
    (45, "Quảng Trị",           "Miền Trung", 1),
    (46, "Thừa Thiên Huế",      "Miền Trung", 1),
    (48, "Đà Nẵng",             "Miền Trung", 1),
    (49, "Quảng Nam",           "Miền Trung", 1),
    (51, "Quảng Ngãi",          "Miền Trung", 1),
    (52, "Bình Định",           "Miền Trung", 1),
    (54, "Phú Yên",             "Miền Trung", 1),
    (56, "Khánh Hòa",           "Miền Trung", 1),
    (58, "Ninh Thuận",          "Miền Trung", 1),
    (60, "Bình Thuận",          "Miền Trung", 1),
    (62, "Kon Tum",             "Tây Nguyên", 2),
    (64, "Gia Lai",             "Tây Nguyên", 2),
    (66, "Đắk Lắk",             "Tây Nguyên", 2),
    (67, "Đắk Nông",            "Tây Nguyên", 2),
    (68, "Lâm Đồng",            "Tây Nguyên", 2),
    (70, "Bình Phước",          "Miền Nam",   3),
    (72, "Bà Rịa - Vũng Tàu",  "Miền Nam",   3),
    (74, "Bình Dương",          "Miền Nam",   3),
    (75, "Đồng Nai",            "Miền Nam",   3),
    (77, "Tây Ninh",            "Miền Nam",   3),
    (79, "Hồ Chí Minh",        "Miền Nam",   3),
    (80, "Long An",             "Miền Nam",   3),
    (82, "Tiền Giang",          "Miền Nam",   3),
    (83, "Bến Tre",             "Miền Nam",   3),
    (84, "Trà Vinh",            "Miền Nam",   3),
    (86, "Vĩnh Long",           "Miền Nam",   3),
    (87, "Đồng Tháp",           "Miền Nam",   3),
    (89, "An Giang",            "Miền Nam",   3),
    (91, "Kiên Giang",          "Miền Nam",   3),
    (92, "Cần Thơ",             "Miền Nam",   3),
    (93, "Hậu Giang",           "Miền Nam",   3),
    (94, "Sóc Trăng",           "Miền Nam",   3),
    (95, "Bạc Liêu",            "Miền Nam",   3),
    (96, "Cà Mau",              "Miền Nam",   3),
]


def generate(seed: int = 42, **kwargs) -> pd.DataFrame:
    df = pd.DataFrame(PROVINCES, columns=["province_id", "province_name", "region", "region_idx"])
    return df


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


if __name__ == "__main__":
    df = generate()
    out = Path("data/raw/dim_province.parquet")
    write(df, out)
    print(f"dim_province: {len(df)} rows → {out}")
