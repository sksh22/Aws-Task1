import boto3
import os
import urllib.parse  
from concurrent.futures import ThreadPoolExecutor, as_completed

s3 = boto3.client("s3")
MULTIPART_THRESHOLD = 5_000_000_000  
PART_SIZE = 100 * 1024 * 1024               
MAX_WORKERS = 5

def copy_part(
    source_bucket,
    destination_bucket,
    object_key,
    upload_id,
    part_number,
    start_byte,
    end_byte
):
    response = s3.upload_part_copy(
        Bucket=destination_bucket,
        Key=object_key,
        PartNumber=part_number,
        UploadId=upload_id,
        CopySource={ "Bucket": source_bucket, "Key": object_key},
        CopySourceRange=f"bytes={start_byte}-{end_byte}")
    return {
        "PartNumber": part_number,
        "ETag": response["CopyPartResult"]["ETag"] }

def lambda_handler(event, context):
    try:
        source_bucket = event["Records"][0]["s3"]["bucket"]["name"]
        object_key = urllib.parse.unquote_plus(event["Records"][0]["s3"]["object"]["key"])
        destination_bucket = os.environ["DESTINATION_BUCKET"]

        response = s3.head_object(               
            Bucket=source_bucket,
            Key=object_key)
        file_size = response["ContentLength"]
        print(f"File size: {file_size} bytes")

        # For files up to 5 GB
        if file_size <= MULTIPART_THRESHOLD:
            s3.copy_object(
                Bucket=destination_bucket,
                Key=object_key,
                CopySource={"Bucket": source_bucket,"Key": object_key})
            print("File copied successfully using normal copy.")

        # For files larger than 5 GB
        else:
            print("Large file detected. Starting multipart copy.")
            multipart = s3.create_multipart_upload(Bucket=destination_bucket,Key=object_key)
            upload_id = multipart["UploadId"]
            parts = []
            try:
                part_ranges = []
                part_number = 1
                start_byte = 0
                while start_byte < file_size:
                    end_byte = min(start_byte + PART_SIZE - 1,file_size - 1)
                    print(f"Copying part {part_number}: " f"{start_byte} - {end_byte}")
                    part_ranges.append(
                        ( part_number,start_byte,end_byte))
                    start_byte = end_byte + 1
                    part_number += 1

                print(f"Total parts: {len(part_ranges)}")

                # Copy parts in parallel
                with ThreadPoolExecutor(
                    max_workers=MAX_WORKERS
                ) as executor:
                    futures = []
                    for part_number, start_byte, end_byte in part_ranges:
                        future = executor.submit(
                            copy_part,
                            source_bucket,
                            destination_bucket,
                            object_key,
                            upload_id,
                            part_number,
                            start_byte,
                            end_byte)
                        futures.append(future)

                    for future in as_completed(futures):
                        part = future.result()
                        parts.append(part)
                        print(f"Part {part['PartNumber']} copied successfully.")

                parts.sort(
                    key=lambda x: x["PartNumber"])
                
                s3.complete_multipart_upload(
                    Bucket=destination_bucket,
                    Key=object_key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts})
                print("Large file copied successfully.")

            except Exception as e:
                s3.abort_multipart_upload(
                    Bucket=destination_bucket,
                    Key=object_key,
                    UploadId=upload_id)
                print(f"Multipart copy failed: {e}")
                raise

    except Exception as e:
        print(f"Error copying file: {e}")
        raise