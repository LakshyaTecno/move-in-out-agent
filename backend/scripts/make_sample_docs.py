"""Generate fictional sample documents for testing AI document verification.

Every image is watermarked SPECIMEN and uses made-up names and numbers; none
copies a real government design. Run from backend/:
    uv run python scripts/make_sample_docs.py
Output: ../samples/documents/*.png
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[2] / "samples" / "documents"


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


def watermark(img: Image.Image) -> Image.Image:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    label, f = "SPECIMEN - FOR TESTING ONLY", font(max(40, img.width // 15))
    left, top, right, bottom = f.getbbox(label)
    text = Image.new("RGBA", (right - left + 20, bottom - top + 20), (0, 0, 0, 0))
    ImageDraw.Draw(text).text((10 - left, 10 - top), label, font=f, fill=(200, 30, 30, 80))
    text = text.rotate(25, expand=True)
    layer.paste(text, ((img.width - text.width) // 2, (img.height - text.height) // 2), text)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def card(filename: str, title: str, rows: list[tuple[str, str]], size=(1000, 620)) -> None:
    """A small ID-style card."""
    img = Image.new("RGB", size, (245, 247, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, size[0], 90], fill=(40, 70, 120))
    d.text((30, 25), title, font=font(38), fill="white")
    d.rectangle([30, 130, 230, 370], outline=(120, 120, 120), width=3)
    d.text((70, 235), "PHOTO", font=font(30), fill=(150, 150, 150))
    y = 130
    for label, value in rows:
        d.text((270, y), f"{label}:", font=font(26), fill=(90, 90, 90))
        d.text((520, y), value, font=font(30), fill=(20, 20, 20))
        y += 62
    watermark(img).save(OUT / filename)


def letter(filename: str, title: str, paragraphs: list[str], size=(900, 1150)) -> None:
    """A full-page letter or deed."""
    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    d.text((60, 60), title, font=font(42), fill=(20, 20, 20))
    d.line([60, 125, size[0] - 60, 125], fill=(60, 60, 60), width=3)
    y = 170
    for para in paragraphs:
        line = ""
        for word in para.split():
            if d.textlength(line + " " + word, font=font(26)) > size[0] - 120:
                d.text((60, y), line.strip(), font=font(26), fill=(30, 30, 30))
                y += 40
                line = ""
            line += " " + word
        d.text((60, y), line.strip(), font=font(26), fill=(30, 30, 30))
        y += 70
    watermark(img).save(OUT / filename)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # --- Asha Rao: owner moving into A-101 (all correct) ---
    card("asha_id_proof.png", "IDENTITY CARD (SAMPLE)",
         [("Name", "Asha Rao"), ("Date of birth", "14-02-1988"), ("ID number", "SMPL-4821-0007"), ("Valid until", "2034-12-31")])
    letter("asha_sale_deed.png", "SALE DEED (SAMPLE)", [
        "This deed of sale is made on 12 January 2024 between Green Valley Developers (the Seller) and Asha Rao (the Buyer).",
        "The Seller sells to the Buyer the residential flat A-101, Green Valley Residency, together with one covered parking space.",
        "Buyer: Asha Rao. Registration no. SMPL/SD/2024/0042.",
        "Signed: Asha Rao (Buyer)      Signed: Green Valley Developers (Seller)",
    ])

    # --- Karan Shah: tenant moving into B-302 (correct set) ---
    card("karan_id_proof.png", "IDENTITY CARD (SAMPLE)",
         [("Name", "Karan Shah"), ("Date of birth", "03-07-1993"), ("ID number", "SMPL-7730-0151"), ("Valid until", "2033-06-30")])
    letter("karan_rental_agreement.png", "RENTAL AGREEMENT (SAMPLE)", [
        "This rental agreement is made on 1 October 2026 between Rajesh Kumar (the Owner) and Karan Shah (the Tenant).",
        "The Owner lets flat B-302, Green Valley Residency to the Tenant for a period of eleven months at a monthly rent of Rs 32,000.",
        "Valid until: 2027-08-31. Registration no. SMPL/RA/2026/1187.",
        "Signed: Rajesh Kumar (Owner)      Signed: Karan Shah (Tenant)",
    ])
    letter("karan_police_verification.png", "POLICE VERIFICATION CERTIFICATE (SAMPLE)", [
        "This is to certify that Karan Shah, residing at B-302, Green Valley Residency, has been verified as a tenant.",
        "No adverse record was found. Certificate no. SMPL/PV/2026/3391.",
        "Issued: 5 October 2026. Valid until: 2027-10-04.",
        "Station officer (sample signature)",
    ])
    letter("karan_owner_noc.png", "NO OBJECTION CERTIFICATE (SAMPLE)", [
        "I, Rajesh Kumar, owner of flat B-302, Green Valley Residency, have no objection to Karan Shah moving into the flat as my tenant.",
        "Date: 2 October 2026.",
        "Signed: Rajesh Kumar (Owner)",
    ])

    # --- Rahul Mehta: tenant moving OUT of A-201, Green Valley ---
    card("rahul_id_proof.png", "IDENTITY CARD (SAMPLE)",
         [("Name", "Rahul Mehta"), ("Date of birth", "21-11-1990"), ("ID number", "SMPL-3304-0219"), ("Valid until", "2032-03-31")])
    letter("rahul_owner_noc_moveout.png", "NO OBJECTION CERTIFICATE (SAMPLE)", [
        "I, Sunita Verma, owner of flat A-201, Green Valley Residency, have no objection to my tenant Rahul Mehta vacating the flat and moving out his belongings.",
        "The tenancy ends on 31 October 2026. Date: 12 October 2026.",
        "Signed: Sunita Verma (Owner)",
    ])

    # --- Priya Nair: owner moving OUT of A-202, Green Valley (has dues) ---
    card("priya_id_proof.png", "IDENTITY CARD (SAMPLE)",
         [("Name", "Priya Nair"), ("Date of birth", "09-05-1985"), ("ID number", "SMPL-6612-0088"), ("Valid until", "2031-09-30")])

    # --- Rohan Gupta: tenant moving INTO 102, Sunrise Heights ---
    card("rohan_id_proof.png", "IDENTITY CARD (SAMPLE)",
         [("Name", "Rohan Gupta"), ("Date of birth", "17-08-1995"), ("ID number", "SMPL-9045-0332"), ("Valid until", "2035-01-31")])
    letter("rohan_rental_agreement.png", "RENTAL AGREEMENT (SAMPLE)", [
        "This rental agreement is made on 5 October 2026 between Meena Iyer (the Owner) and Rohan Gupta (the Tenant).",
        "The Owner lets flat 102, Sunrise Heights to the Tenant for a period of eleven months at a monthly rent of Rs 18,000.",
        "Valid until: 2027-09-04. Registration no. SMPL/RA/2026/2045.",
        "Signed: Meena Iyer (Owner)      Signed: Rohan Gupta (Tenant)",
    ])

    # --- Neha Kapoor: tenant moving OUT of 201, Sunrise Heights (dues only warn here) ---
    card("neha_id_proof.png", "IDENTITY CARD (SAMPLE)",
         [("Name", "Neha Kapoor"), ("Date of birth", "30-01-1992"), ("ID number", "SMPL-2278-0461"), ("Valid until", "2033-11-30")])
    letter("neha_owner_noc_moveout.png", "NO OBJECTION CERTIFICATE (SAMPLE)", [
        "I, Vivek Malhotra, owner of flat 201, Sunrise Heights, have no objection to my tenant Neha Kapoor vacating the flat.",
        "Pending maintenance dues may be adjusted against the security deposit. Date: 10 October 2026.",
        "Signed: Vivek Malhotra (Owner)",
    ])

    # --- Arjun Das: owner moving OUT of 202, Sunrise Heights ---
    card("arjun_id_proof.png", "IDENTITY CARD (SAMPLE)",
         [("Name", "Arjun Das"), ("Date of birth", "12-12-1980"), ("ID number", "SMPL-1190-0507"), ("Valid until", "2030-06-30")])

    # --- Deliberately WRONG documents for negative tests ---
    letter("BAD_karan_owner_noc_wrong_name.png", "NO OBJECTION CERTIFICATE (SAMPLE)", [
        "I, Rajesh Kumar, owner of flat B-302, Green Valley Residency, have no objection to Karan Shaw moving into the flat as my tenant.",
        "Date: 2 October 2026.",
        "Signed: Rajesh Kumar (Owner)",
    ])
    letter("BAD_karan_police_verification_expired.png", "POLICE VERIFICATION CERTIFICATE (SAMPLE)", [
        "This is to certify that Karan Shah, residing at B-302, Green Valley Residency, has been verified as a tenant.",
        "No adverse record was found. Certificate no. SMPL/PV/2025/1102.",
        "Issued: 1 September 2025. Valid until: 2026-08-31.",
        "Station officer (sample signature)",
    ])
    letter("BAD_grocery_receipt.png", "FRESH MART - RECEIPT", [
        "Milk 2 x Rs 30 ........ Rs 60",
        "Bread 1 x Rs 45 ....... Rs 45",
        "Eggs 12 x Rs 7 ........ Rs 84",
        "TOTAL ................. Rs 189      Thank you for shopping!",
    ], size=(900, 700))

    for p in sorted(OUT.glob("*.png")):
        print(p.relative_to(OUT.parents[1]))


if __name__ == "__main__":
    main()
