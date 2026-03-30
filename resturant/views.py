from django.shortcuts import render
from rest_framework import generics
from django.http import HttpResponse
from .models import ProductModel
from .serializers import ProductSerializer
from django.http import StreamingHttpResponse
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

from ollama import chat
from rest_framework.response import Response

# Create your views here.



class ProductList(generics.ListCreateAPIView):
    queryset = ProductModel.objects.all()
    serializer_class = ProductSerializer
    
    
    
class ChatView(generics.GenericAPIView):

    def post(self, request, *args, **kwargs):
         # -------------------------
        # 0. Get user query
        # -------------------------
        user_qn = request.data.get('message', '').lower()

        # -------------------------
        # 1. Detect intent
        # -------------------------
        is_description_query = any(word in user_qn for word in ["description", "about", "details"])
        is_price_query = "price" in user_qn or "how much" in user_qn
        is_list_of_products_query = any(word in user_qn for word in ["list", "all products", "menu"])

        # -------------------------
        # 2. Clean query
        # -------------------------
        STOP_WORDS = [
            "what", "is", "the", "of", "price", "how", "much",
            "description", "discriptions", "tell", "me", "about",
            "list", "all", "products", "menu"
        ]

        keywords = [word for word in user_qn.split() if word not in STOP_WORDS]
        clean_query = " ".join(keywords) if keywords else user_qn

        # -------------------------
        # 3. Search DB
        # -------------------------
        search_vector = SearchVector('title', weight='A') + SearchVector('discriptions', weight='B')
        search_query = SearchQuery(clean_query)

        if not clean_query.strip() and is_price_query:
            # fallback: return all items if query is empty but user wants price
            queryset = ProductModel.objects.all()
        else:
            queryset = ProductModel.objects.annotate(
                rank=SearchRank(search_vector, search_query)
            ).filter(rank__gte=0.1).order_by('-rank')

        # -------------------------
        # 4. Return based on intent
        # -------------------------
        if is_price_query:
            data = list(queryset.values('title', 'price'))
        elif is_description_query:
            data = list(queryset.values('title', 'discriptions'))
        elif is_list_of_products_query:
            data = ProductModel.objects.all().values('title', 'price', 'discriptions')
        else:
            data = list(queryset.values('title', 'price', 'discriptions'))
        print("Extracted data from DB:", data)  # Debug: Print the extracted data

        # Sort for consistent output
        data = sorted(data, key=lambda x: x['title'])

        # -------------------------
        # 5. Handle empty results
        # -------------------------
        if not data:
            return Response({"response": "No matching items found"})

        # -------------------------
        # 6. Format data for prompt
        # -------------------------
        formatted_data = "\n".join([
            f"{item['title']}: {item.get('price','')} TZS - {item.get('discriptions','')}"
            for item in data
        ])

        # -------------------------
        # 7. Construct LLM prompt
        # -------------------------
        prompt = f"""
You are a friendly restaurant assistant.

STRICT RULES:
- Answer naturally like a human (not robotic)
- Do NOT say "based on the provided data"
- Do NOT explain yourself
- Just give the answer directly
- If no data, say: "No matching items found"
- Do NOT use your own knowledge
- Do NOT guess or estimate prices
- If the user asks for a price but only description is available, say: "Price not available, but here is the description: [description]"
- If the user asks for a description but only price is available, say: "Description not available, but the price is: [price]"
- Include emojis in your response to make it more friendly and engaging, at least 2 emojis in each response, and add a relevant emoji at the end.

User question:
{user_qn}

Menu:
{formatted_data}
"""
        def generate():
            response = chat(
                model="smollm2",
                messages=[{"role": "user", "content": prompt}],
                stream=True
            )

            for chunk in response:
                    # Debug: Print the extracted content
                content = chunk.message.content
                # print(chunk.message.content,end="",flush=True)  # Print without newline and flush immediately
                yield content

        return StreamingHttpResponse(generate(), content_type="text/plain")