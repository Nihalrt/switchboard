package routing

import "hash/fnv"

func BucketFor(DeviceID string, flagName string) int {

	combined := flagName + DeviceID

	// This function will be used to convert the combined string to a hash number and it's being passed as bytes to the hasher
	hasher := fnv.New32a()
	hasher.Write([]byte(combined))

	hashValue := hasher.Sum32()
	bucket := int(hashValue%100) + 1

	return bucket
}
