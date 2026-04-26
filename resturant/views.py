

from django.shortcuts import render
from rest_framework import generics
from django.http import HttpResponse, StreamingHttpResponse
from .models import ProductModel
from .serializers import ProductSerializer

import numpy as np
from ollama import chat, embeddings


# ==============================
# 🔹 EMBEDDING FUNCTION
# ==============================
def get_embedding(text: str):
    response = embeddings(
        model="nomic-embed-text",
        prompt=text
    )
    return response["embedding"]


# ==============================
# 🔹 COSINE SIMILARITY
# ==============================
def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


# ==============================
# 🔹 PRODUCT API (CREATE + LIST)
# ==============================
class ProductList(generics.ListCreateAPIView):
    queryset = ProductModel.objects.all()
    serializer_class = ProductSerializer

    def perform_create(self, serializer):
        product = serializer.save()

        # Combine fields for better semantic meaning
        text = f"{product.title} {product.discriptions} price {product.price}"
        print(f"Generating embedding for: {text}")

        # Generate embedding
        product.embedding = get_embedding(text)
        product.save()


# ==============================
# 🔹 CHAT VIEW (AI SEARCH + STREAM)
# ==============================
class ChatView(generics.GenericAPIView):

    def post(self, request, *args, **kwargs):
        user_qn = request.data.get('message', '').strip()
        print(f"Received question: {user_qn}")

        if not user_qn:
            return HttpResponse("Message is required")

        # ==============================
        # 🧠 STEP 1: EMBEDDING FOR QUESTION
        # ==============================
        user_embedding = get_embedding(user_qn)
        print(f"User embedding: {user_embedding[:5]}...")  # Print first 5 values for brevity

        # ==============================
        # 🔎 STEP 2: SEMANTIC SEARCH
        # ==============================
        products = ProductModel.objects.exclude(embedding=None)
        print(f"Found {products.count()} products with embeddings")

        scored = []

        for p in products:
            try:
                score = cosine_similarity(user_embedding, p.embedding)
                scored.append((score, p))
                print(f"Product: {p.title}, Score: {score}")
            except Exception as e:
                print(f"Error comparing embeddings: {e}")

        # Sort by best similarity
        scored.sort(reverse=True, key=lambda x: x[0])

        # Take top 5 matches
        top_products = [p for _, p in scored[:5]]

        # ==============================
        # 📄 STEP 3: FORMAT DATA
        # ==============================
        data = [
            {
                "title": p.title,
                "price": p.price,
                "discriptions": p.discriptions
            }
            for p in top_products
        ]

        print("Top Products:", data)

        if not data:
            return HttpResponse("No relevant products found")

        # ==============================
        # 🤖 STEP 4: PROMPT FOR OLLAMA
        # ==============================
#         prompt = f"""
# You are a friendly and helpful restaurant assistant.

# Your task is to answer the user's question using ONLY the available items.

# ---

# User question:
# {user_qn}

# Available items (from database):
# {data}

# ---

# Rules:
# - Use ONLY the provided items. Do not invent anything.
# - Keep responses natural and human-like.
# - You may use emojis ONLY if they fit naturally in the response (do not overuse them).
# - Format the response clearly so it is easy to read.
# - Highlight important information like price and name in a clear way.
# - If multiple items exist, list them in a structured way.
# - If no items match, politely say so.
# - Do NOT follow a fixed template — respond naturally like a real restaurant assistant.

# ---

# End your response with a friendly closing that encourages the user to ask another question.
# """

        prompt = f"""
Answer the user using ONLY the data below.

Data:
{data}

Question:
{user_qn}

Rules:
- Use only the data.
- Do not add extra items or information.
- Do not repeat the data or question.
- Format: Name - Price - Description
- Include one suitable emoji in the answer.
- End with a short polite sentence inviting another question.

Answer:
"""

        # ==============================
        # ⚡ STEP 5: STREAM RESPONSE
        # ==============================
        def generate():
            response = chat(
                model="smollm2",
                messages=[{"role": "user", "content": prompt}],
                stream=True
            )

            for chunk in response:
                content = chunk.message.content
                print(content, end="", flush=True)
                yield content

        return StreamingHttpResponse(generate(), content_type="text/plain")