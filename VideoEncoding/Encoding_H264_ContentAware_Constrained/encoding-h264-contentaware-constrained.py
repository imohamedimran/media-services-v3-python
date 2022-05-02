#<EncodingImports>
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.mgmt.media import AzureMediaServices
from azure.storage.blob import BlobServiceClient
from azure.mgmt.media.models import (
  Asset,
  Transform,
  TransformOutput,
  BuiltInStandardEncoderPreset,
  PresetConfigurations,
  InterleaveOutput,
  Job,
  JobInputAsset,
  JobOutputAsset,
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
uniqueness = "contentAware264Constrained"

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
print(f"Uploading the file {source_file}")

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
transform_name = 'H264EncodingContentAwareConstrained'

# Create a new BuiltIn Standard encoding Transform for H264 ContentAware Constrained
print(f"Creating Standard Encoding transform named: {transform_name}")

# This sample uses constraints on the CAE encoding preset to reduce the number of tracks output and resolutions to a specific range.
# First we will create a PresetConfigurations object to define the constraints that we want to use
# This allows you to configure the encoder settings to control the balance between speed and quality. Example: set Complexity as Speed for faster encoding but less compression efficiency.

presetConfig = PresetConfigurations(
    complexity="Speed",
    # The output includes both audio and video.
    interleave_output=InterleaveOutput.INTERLEAVED_OUTPUT,
    # The key frame interval in seconds. Example: set as 2 to reduce the playback buffering for some players.
    key_frame_interval_in_seconds= 2,
    # The maximum bitrate in bits per second (threshold for the top video layer). Example: set max_bitrate_bps as 6000000 to avoid producing very high bitrate outputs for contents with high complexity
    max_bitrate_bps= 6000000,
    # The minimum bitrate in bits per second (threshold for the bottom video layer). Example: set min_bitrate_bps as 200000 to have a bottom layer that covers users with low network bandwidth.
    min_bitrate_bps= 200000,
    #The maximum height of output video layers. Example: set max_height as 720 to produce output layers up to 720P even if the input is 4K.
    max_height= 720,
    # The minimum height of output video layers. Example: set min_height as 360 to avoid output layers of smaller resolutions like 180P.
    min_height=270,
    #  The maximum number of output video layers. Example: set max_layers as 4 to make sure at most 4 output layers are produced to control the overall cost of the encoding job.
    max_layers=3   
)

# From SDK
# TransformOutput(*, preset, on_error=None, relative_priority=None, **kwargs) -> None
# For this snippet, we are using 'BuiltInStandardEncoderPreset'

transform_output = TransformOutput(
  preset = BuiltInStandardEncoderPreset(
    preset_name = "ContentAwareEncoding",
    # Configurations can be used to control values used by the Content Aware Encoding Preset.
    configurations = presetConfig
  ),
  # What should we do with the job if there is an error?
  on_error=OnErrorType.STOP_PROCESSING_JOB,
  # What is the relative priority of this job to others? Normal, high or low?
  relative_priority=Priority.NORMAL
)

print("Creating encoding transform...")

# Adding transform details
myTransform = Transform()
myTransform.description="H264 content aware encoding with configuration settings"
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
job_name = 'MyEncodingH264ContentAwareConstrainedJob'+ uniqueness
print(f"Creating Encoding264ContentAwareConstrained job {job_name}")
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