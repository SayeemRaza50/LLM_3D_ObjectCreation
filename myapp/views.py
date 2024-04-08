from django.shortcuts import render
from django.http import JsonResponse
import os
import requests
import base64
import random
import json
from PIL import Image
import fitz

# Create your views here.

def process(request):
    if request.method == 'POST':
        pdf_file = request.FILES.get('pdf_file')
        instructions = request.POST.get('instructions', '')

        ten_digit_random = random.randint(1000000000, 9999999999)

        if pdf_file:
            with open(f'./myapp/data/{ten_digit_random}.pdf', 'wb') as destination:
                for chunk in pdf_file.chunks():
                    destination.write(chunk)
            
            pdf_folder = "./myapp/data"
            output_folder = "./myapp/output"
            save_folder = "./myapp/text_outputs"

            os.makedirs(output_folder, exist_ok=True)
            os.makedirs(save_folder, exist_ok=True)

            responses = process_pdfs(pdf_folder, output_folder, save_folder, instructions, ten_digit_random)

            for i, response in enumerate(responses):
                print(f"Response {i+1}: {response}")

            remove_specific_files(pdf_folder, ten_digit_random, output_folder)
            
            return JsonResponse(responses[0])
        else:
            return JsonResponse({'status': 'error', 'message': 'No PDF file provided'})

    return render(request, 'index.html')

def remove_specific_files(pdf_folder, random_number, output_folder):
    pdf_path = os.path.join(pdf_folder, f"{random_number}.pdf")
    
    # Remove uploaded PDF file
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    # Remove associated PNG images
    for file_name in os.listdir(output_folder):
        if file_name.startswith(f"out_{random_number}"):
            file_path = os.path.join(output_folder, file_name)
            if os.path.exists(file_path):
                os.remove(file_path)

def convert_pdf_to_images(pdf_path):
    doc = fitz.open(pdf_path)
    pages = [doc.load_page(i) for i in range(doc.page_count)]
    return pages

def save_pdf_as_png(pages, output_folder, random_number):
    for i, page in enumerate(pages):
        pixmap = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72))

        # Updated code to save as PNG using Pillow
        image_path = os.path.join(output_folder, f"out_{random_number}.png")
        img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        img.save(image_path)

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def process_pdfs(pdf_folder, output_folder, save_folder, instructions, random_number):
    openai_responses = []

    for pdf_file in os.listdir(pdf_folder):
        retry = 0
        while retry < 3:
            try:
                if pdf_file.endswith(".pdf"):
                    pdf_path = os.path.join(pdf_folder, pdf_file)
                    
                    # Step 2: Convert PDF to images
                    pdf_images = convert_pdf_to_images(pdf_path)


                    # Step 3: Save PDF as .png
                    save_pdf_as_png(pdf_images, output_folder, random_number)

                    # Step 4: Encode image to base64
                    image_path = os.path.join(output_folder, f"out_{random_number}.png")  # Assuming you want to use the first page
                    base64_image = encode_image(image_path)
                    # Step 5: Call OpenAI GPT-4 Vision API
                    response = openai_gpt4_vision_request(base64_image, instructions)

                    print(response)
                    
                    print(pdf_file)
                    save_path = os.path.join(save_folder, f"{pdf_file.replace('.pdf', '_output.txt')}")
                    with open(save_path, 'w', encoding='utf-8') as file:
                        file.write(str(response["choices"][0]["message"]["content"]))

                    output = json.loads(response["choices"][0]["message"]["content"])
                    openai_responses.append(output)
                    print(f"{response['choices'][0]['message']['content']}")
                    break
            except Exception as e:
                print(f"Error processing {pdf_file}: {e}")
                retry += 1
                if retry == 3:
                    print(f"Failed to process {pdf_file} after 3 retries")

    return openai_responses


def openai_gpt4_vision_request(base64_image, vertices):
    openai_api_key = ""  # Replace with your OpenAI API key
    model_name = "gpt-4-vision-preview"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }

    output_example = """
        {
            "Vertices" : [[0,0,0],[0,0,20],[0,100,0],[0,100,20],[50,0,0],[50,0,20],[50,100,0],[50,100,20],[50,50,0],[50,50,20],[50,85,0],[50,85,20],[100,50,0],[100,50,20],[100,85,0],[100,85,20]],
            "Triangles" : [0,1,2,2,1,3,4,5,6,6,5,7,0,2,4,4,2,6,1,3,5,5,3,7,0,1,4,4,1,5,2,3,6,6,3,7,0,4,1,1,4,5,2,6,3,3,6,7,8,9,10,10,9,11,8,10,12,12,10,14,9,11,13,13,11,15,8,12,9,9,12,13,10,14,11,11,14,15],
            "AIResponse" : "Description of the output... .. .."
        }
    """

    prompt = f"""Your an expert mathematician, You can estimate triangles of parallelepiped and output as a json. Please give the point in 3D demension.\nPlease Add no description only give out the JSON.
    Description for input Structure:
    1. Given A parallelepiped in 3D space.
    2. There are 3 diagrams in this image. Each is representation of same parallelpiped from different angles. Each sub digram is labbeled with a number from same color as the digram is represented with.
    3. This is complex diagram made of small simple diagrams. These simple digrams are represented by different colors (red, yellow)
    4. The diagram also contains line lengths of parallelepiped. Represented by black lines. 
    5. The vertices of parallelepiped are given below to calculate the triangles parallelepiped.
    6. The parallelepid is symmetrical and are not hollow.
    7. Please calculate the triangles of parallelepiped and output as a json.
    8. The vertices of parallelepiped are given below to calculate the triangles parallelepiped.

    \n\n
    Vertices of Given parallelepiped:
    {vertices}
    \n\n 

    Important Instructions:
    1. Please focus on image for validation of calculation of triangles of parallelepiped. Also in any case do not make parallelepiped howllow
    2. Please reevaluate if all the vertices are being used in triangle calculations
    3. Also try to make simple shapes before constructing them into larger picture. Please focus on each color saperately.
    4. Please make sure that the triangles are not hollow and are valid. The Shape is a solid shape not a with wholes. Please calculate proper triangles covering full shape to make solid.

    Note: Please focus more on calculating triangles for the parallelepiped and less on the description of the parallelepiped.
    
    \n\n
    Expected Output:
    
    1. Vertices of parallelpiped. (Dont use floating points)
    2. Triangles of parallelpiped.
    3. Description

    \n\n
    Description for output Structure:
    
    1. Do not include any comments
    2. Do not include calculations and provide raw data
    3. Make sure that the triangle data you provide has integer values that should be less than total number of vertices in the shape. Also please make sure no triangles make parallepid hollow
    4. Do not Write json/or any description on top or bottom of output.
    5. Vertices should be an array of arrays with 3 elements each.
    6. Triangles should be an array of integers.
    7. The output should be in JSON format.
    8. Each parameter should be in a exact one separate line. Do not include any extra lines or prettify the output.

    \n\n
    
    

    Example:\n
    {output_example}
    \n\n

    Important Note:Please do not Add any description only give out the JSON.

    """

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1000,
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    return response.json()
