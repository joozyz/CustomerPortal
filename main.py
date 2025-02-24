from app import app

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, debug=True)
    except Exception as e:
        print(f"Error starting Flask server: {str(e)}")
        raise