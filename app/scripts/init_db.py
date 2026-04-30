from app.core.database import create_database


def main() -> None:
    create_database()
    print("Database created successfully.")


if __name__ == "__main__":
    main()