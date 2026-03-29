from django.shortcuts import render
from rest_framework import generics
from django.http import HttpResponse
from .models import ProductModel
from .serializers import ProductSerializer
from django.http import StreamingHttpResponse
from ollama import chat
# Create your views here.



class ProductList(generics.ListCreateAPIView):
    queryset = ProductModel.objects.all()
    serializer_class = ProductSerializer
    

class ChatView(generics.GenericAPIView):

    def post(self, request, *args, **kwargs):
        # Get user input correctly
        user_qn = request.data.get('message', '')
        
        #here we will use the user_qn to query the database and get relevant data to feed into the model for generating a response. 
        
        # Query DB
        queryset = ProductModel.objects.filter(title__icontains=user_qn)

        # Convert queryset to readable text
        data = list(queryset.values('title', 'price', 'discriptions'))

        prompt = f"""
You are a helpful assistant for restaurant management.

User question:
{user_qn}

Answer ONLY using this data:
{data}
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
                print(chunk.message.content,end="",flush=True)  # Print without newline and flush immediately
                yield content

        return StreamingHttpResponse(generate(), content_type="text/plain")