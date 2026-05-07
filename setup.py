"""
Script setup awal — jalankan sekali setelah clone.
"""
import os
import shutil

def main():
    # Buat .env dari example
    if not os.path.exists(".env"):
        shutil.copy(".env.example", ".env")
        print("✓ File .env dibuat dari .env.example")
        print("  → Isi kredensial di .env sebelum menjalankan agent!")
    else:
        print("✓ File .env sudah ada")

    # Buat direktori yang dibutuhkan
    for d in ("output", "logs"):
        os.makedirs(d, exist_ok=True)
        print(f"✓ Direktori '{d}' siap")

    print("\nSetup selesai. Langkah selanjutnya:")
    print("  1. Edit file .env dengan kredensial Anda")
    print("  2. pip install -r requirements.txt")
    print("  3. python main.py preview      ← coba generate konten")
    print("  4. python main.py jadwal       ← jalankan scheduler otomatis")

if __name__ == "__main__":
    main()
