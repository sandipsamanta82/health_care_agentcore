
FROM public.ecr.aws/docker/library/python:3.13-alpine

# Ensure dependencies are installed
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080
CMD ["python", "lg_agent_async_approval.py"]