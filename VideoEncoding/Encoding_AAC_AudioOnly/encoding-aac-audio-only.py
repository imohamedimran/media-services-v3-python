#<EncodingImports>
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.mgmt.media import AzureMediaServices
from azure.storage.blob import BlobServiceClient
from azure.mgmt.media.models import (
  Asset,
  Transform,
  TransformOutput,
  StandardEncoderPreset,
  Job,
  JobInputAsset,
  JobOutputAsset,
  AacAudio,
  Mp4Format,
  AacAudioProfile,
  OnErrorType,
  Priority
)
import os

#Timer for checking job progress
import time
#</EncodingImports>

#<ClientEnvironmentVariables>
#Get environment variables
load_dotenv()

# Get the default Azure credential from the environment variables AZURE_CLIENT_ID and AZURE_CLIENT_SECRET and AZURE_TENTANT_ID
default_credential = DefaultAzureCredential()

# Get the environment variables SUBSCRIPTIONID, RESOURCEGROUP and ACCOUNTNAME
SUBSCRIPTION_ID = os.getenv('SUBSCRIPTIONID')
RESOURCE_GROUP = os.getenv('RESOURCEGROUP')
ACCOUNT_NAME = os.getenv('ACCOUNTNAME')

# The file you want to upload.  For this example, put the file in the same folder as this script. 
# The file ignite.mp4 has been provided for you. 
source_file = "ignite.mp4"

# This is a random string that will be added to the naming of things so that you don't have to keep doing this during testing
uniqueness = "encodeAAC-audio-only"

# Set the attributes of the input Asset using the random number
in_asset_name = 'inputassetName' + uniqueness
in_alternate_id = 'inputALTid' + uniqueness
in_description = 'inputdescription' + uniqueness

# Create an Asset object
# From the SDK
# Asset(*, alternate_id: str = None, description: str = None, container: str = None, storage_account_name: str = None, **kwargs) -> None
# The asset_id will be used for the container parameter for the storage SDK after the asset is created by the AMS client.
input_asset = Asset(alternate_id=in_alternate_id,description=in_description)

# Set the attributes of the output Asset using the random number
out_asset_name = 'outputassetName' + uniqueness
out_alternate_id = 'outputALTid' + uniqueness
out_description = 'outputdescription' + uniqueness
# From the SDK
# Asset(*, alternate_id: str = None, description: str = None, container: str = None, storage_account_name: str = None, **kwargs) -> None
output_asset = Asset(alternate_id=out_alternate_id,description=out_description)

# The AMS Client
print("Creating AMS Client")
client = AzureMediaServices(default_credential, SUBSCRIPTION_ID)

# Create an input Asset
print(f"Creating input asset {in_asset_name}")
# From SDK
# create_or_update(resource_group_name, account_name, asset_name, parameters, custom_headers=None, raw=False, **operation_config)
inputAsset = client.assets.create_or_update( RESOURCE_GROUP, ACCOUNT_NAME, in_asset_name, input_asset)

# An AMS asset is a container with a specific id that has "asset-" prepended to the GUID.
# So, you need to create the asset id to identify it as the container
# where Storage is to upload the video (as a block blob)
in_container = 'asset-' + inputAsset.asset_id

# create an output Asset
print(f"Creating output asset {out_asset_name}")
# From SDK
# create_or_update(resource_group_name, account_name, asset_name, parameters, custom_headers=None, raw=False, **operation_config)
outputAsset = client.assets.create_or_update(RESOURCE_GROUP, ACCOUNT_NAME, out_asset_name, output_asset)

### Use the Storage SDK to upload the video ###
print("Uploading the file " + source_file)

blob_service_client = BlobServiceClient.from_connection_string(os.getenv('STORAGEACCOUNTCONNECTION'))

# From SDK
# get_blob_client(container, blob, snapshot=None)
blob_client = blob_service_client.get_blob_client(in_container,source_file)
working_dir = os.getcwd()
print(f"Current working directory: {working_dir}")
upload_file_path = os.path.join(working_dir, source_file)

# WARNING: Depending on where you are launching the sample from, the path here could be off, and not include the BasicEncoding folder. 
# Adjust the path as needed depending on how you are launching this python sample file. 

# Upload the video to storage as a block blob
with open(upload_file_path, "rb") as data:
  # From SDK
  # upload_blob(data, blob_type=<BlobType.BlockBlob: 'BlockBlob'>, length=None, metadata=None, **kwargs)
    blob_client.upload_blob(data)


#<CreateTransform>
transform_name = 'AAC_LC_AudioOnly'

# Create a new Standard encoding Transform for H264
print(f"Creating Standard Encoding transform named: {transform_name}")

# From SDK
# TransformOutput(*, preset, on_error=None, relative_priority=None, **kwargs) -> None
# For this snippet, we are using 'StandardEncoderPreset'

transform_output = TransformOutput(
  preset = StandardEncoderPreset(
    codecs = [
      AacAudio(
        channels=2,
        sampling_rate=48000,
        bitrate=128000,
        profile=AacAudioProfile.AAC_LC,
        label="aac-lc"
      )
    ],
    # Specify the format for the output files - one for video+audio, and another for the thumbnails
    formats = [
      # Mux the AAC audio into MP4 files, using basename, label, bitrate and extension macros
      # Either {Label} or {Bitrate} should suffice
      Mp4Format(
        filename_pattern="Video-{Basename}-{Label}-{Bitrate}{Extension}"
      )
    ]
  ),
  # What should we do with the job if there is an error?
  on_error=OnErrorType.STOP_PROCESSING_JOB,
  # What is the relative priority of this job to others? Normal, high or low?
  relative_priority=Priority.NORMAL
)

print("Creating encoding transform...")

# Adding transform details
myTransform = Transform()
myTransform.description="A simple custom AAC LC only encoding transform"
myTransform.outputs = [transform_output]

print(f"Creating transform {transform_name}")
# From SDK
# Create_or_update(resource_group_name, account_name, transform_name, outputs, description=None, custom_headers=None, raw=False, **operation_config)
transform = client.transforms.create_or_update(
  resource_group_name=RESOURCE_GROUP,
  account_name=ACCOUNT_NAME,
  transform_name=transform_name,
  parameters = myTransform)

print(f"{transform_name} created (or updated if it existed already). ")
#</CreateTransform>

#<CreateJob>
job_name = 'MyEncodingAAC-Audio-Only-Job'+ uniqueness
print("Creating EncodingAACAudioOnly job {job_name}")
files = (source_file)

# From SDK
# JobInputAsset(*, asset_name: str, label: str = None, files=None, **kwargs) -> None
input = JobInputAsset(asset_name=in_asset_name)

# From SDK
# JobOutputAsset(*, asset_name: str, **kwargs) -> None
outputs = JobOutputAsset(asset_name=out_asset_name)

# From SDK
# Job(*, input, outputs, description: str = None, priority=None, correlation_data=None, **kwargs) -> None
theJob = Job(input=input,outputs=[outputs])

# From SDK
# Create(resource_group_name, account_name, transform_name, job_name, parameters, custom_headers=None, raw=False, **operation_config)
job: Job = client.jobs.create(RESOURCE_GROUP,ACCOUNT_NAME,transform_name,job_name,parameters=theJob)
#</CreateJob>

#<CheckJob>
# From SDK
# get(resource_group_name, account_name, transform_name, job_name, custom_headers=None, raw=False, **operation_config)
job_state = client.jobs.get(RESOURCE_GROUP,ACCOUNT_NAME,transform_name,job_name)
# First check
print("First job check")
print(job_state.state)

# Check the state of the job every 10 seconds. Adjust time_in_seconds = <how often you want to check for job state>
def countdown(t):
    while t: 
        mins, secs = divmod(t, 60) 
        timer = '{:02d}:{:02d}'.format(mins, secs) 
        print(timer, end="\r") 
        time.sleep(1) 
        t -= 1
    job_current = client.jobs.get(RESOURCE_GROUP,ACCOUNT_NAME,transform_name,job_name)
    if(job_current.state == "Finished"):
      print(job_current.state)
      # TODO: Download the output file using blob storage SDK
      return
    if(job_current.state == "Error"):
      print(job_current.state)
      # TODO: Provide Error details from Job through API
      return
    else:
      print(job_current.state)
      countdown(int(time_in_seconds))

time_in_seconds = 10
countdown(int(time_in_seconds))
#</CheckJob>