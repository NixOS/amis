import json
import hashlib
import logging
import boto3
import botocore

def upload_ami(nix_store_path, s3_bucket, regions):
    with open(nix_store_path + '/nix-support/image-info.json', 'r') as f:
        image_info = json.load(f)

    image_name = 'nixos-'+ image_info['label'] +'-' + image_info['system']

    ec2 = boto3.client('ec2')
    s3 = boto3.client('s3')

    try:
        logging.info(f'Checking if s3://{s3_bucket}/{image_name} exists')
        s3.head_object(Bucket=s3_bucket, Key=image_name)
    except botocore.exceptions.ClientError as e:
        logging.info(f'Uploading {image_info["file"]} to s3://{s3_bucket}/{image_name}')
        s3.upload_file(image_info['file'], s3_bucket, image_name)
        s3.get_waiter('object_exists').wait(Bucket=s3_bucket, Key=image_name)


    logging.info(f'Importing s3://{s3_bucket}/{image_name} to EC2')
    client_token = hashlib.sha256(image_name.encode()).hexdigest()
    snapshot_import_task = ec2.import_snapshot(
        DiskContainer={
            'Format': 'VHD',
            'UserBucket': { 'S3Bucket': s3_bucket, 'S3Key': image_name },
        },
        ClientToken=client_token
    )
    ec2.get_waiter('snapshot_imported').wait(ImportTaskIds=[snapshot_import_task['ImportTaskId']])

    snapshot_import_tasks = ec2.describe_import_snapshot_tasks(ImportTaskIds=[snapshot_import_task['ImportTaskId']])
    assert len(snapshot_import_tasks['ImportSnapshotTasks']) != 0
    snapshot_import_task = snapshot_import_tasks['ImportSnapshotTasks'][0]
    snapshot_id = snapshot_import_task['SnapshotTaskDetail']['SnapshotId']

    # TODO: delete s3 object

    if image_info['system'] == 'x86_64-linux':
        architecture = 'x86_64'
    elif image_info['system'] == 'aarch64-linux':
        architecture = 'arm64'
    else:
        raise Exception('Unknown system: ' + image_info['system'])

    logging.info(f'Registering image {image_name} with snapshot {snapshot_id}')
    register_image = ec2.register_image(
        Name=image_name,
        Architecture=architecture,
        BootMode=image_info['boot_mode'],
        BlockDeviceMappings=[{
            'DeviceName': '/dev/xvda',
            # TODO: VolumeType default to gp3?
            'Ebs': { 'SnapshotId': snapshot_id },
        }],
        RootDeviceName='/dev/xvda',
        VirtualizationType='hvm',
        EnaSupport=True,
        SriovNetSupport='simple',
    )
    ec2.get_waiter('image_available').wait(ImageIds=[register_image['ImageId']])

    image_ids = {}
    for region in regions:
        client_token = register_image['ImageId'] + register_image['Region'] + region + image_name
        copy_image = ec2.copy_image(
            SourceImageId=register_image['ImageId'],
            SourceRegion=register_image['Region'],
            Region=region,
            Name=image_name,
            ClientToken=client_token,
        )
        image_ids[region] = copy_image['ImageId']
    ec2.get_waiter('image_available').wait(ImageIds=image_ids.values())


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)
    import argparse

    parser = argparse.ArgumentParser(description='Upload NixOS AMI to AWS')
    parser.add_argument('nix_store_path', help='Path to nix store')
    parser.add_argument('s3_bucket', help='S3 bucket to upload to')
    parser.add_argument('regions', nargs='+', help='Regions to upload to')
    args = parser.parse_args()

    upload_ami(args.nix_store_path, args.s3_bucket, args.regions)