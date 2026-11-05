import uvicorn

if __name__ == "__main__":
    print("=" * 70)
    print("   HOSTEL & TRANSPORT RULES ASSISTANT")
    print("   Evidence-Grounded RAG & Policy Verification System")
    print("=" * 70)
    print("Starting server on http://127.0.0.1:8000")
    print("API Documentation: http://127.0.0.1:8000/docs")
    print("-" * 70)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

