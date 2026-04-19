import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name="da3hc6qxp",
    api_key="943549291431879",
    api_secret="JZ7OEMiuGlTXBdv3Q6sk_4qMcfE"
)

print("Testing Cloudinary connection...")
try:
    result = cloudinary.uploader.upload(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/200px-PNG_transparency_demonstration_1.png",
        folder="test"
    )
    print("Success! Uploaded:", result["secure_url"])
except Exception as e:
    print("Error:", str(e))
    import traceback
    traceback.print_exc()
