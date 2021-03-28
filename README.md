# MiniDFS
MiniDFS simulated by python implementation.
The project is mainly based on [MiniDFS](https://github.com/HawkAaron/MiniDFS/), with several advanced functions added.

## Basic functions (Originally provided by  [MiniDFS](https://github.com/HawkAaron/MiniDFS/))
* Read/write a file
* Move file and manage directory
* File Slicing
* Replication
* List file tree
## Advanced functions (Extensions)
* List meta-info of Chunks
* List meta-info of Replicas
* File integrity check
* Recover chunks
* Recover servers
* DFS formatting
* Delete file


## Instructions
1. Run main.py to start:
	`python main.py`
	
2. Commands：
	```bash
	# list all files in DFS, return id, name, size
	MiniDFS > ls

	# list file tree in DFS
	MiniDFS > ls2
	
	# make dir in DFS
	MiniDFS > mkdir file_dir

	# upload local file to DFS, return file id
	MiniDFS > put source_file_path

	# upload local file to DFS dir, return file id
	MiniDFS > put2 source_file_path dest_dir

	# read file in DFS
	MiniDFS > read file_id offset count
	
	# read file using dir
	MiniDFS > read2 dir/file_name offset count

	# download file in DFS
	MiniDFS > fetch file_id save_path
	
	# download using dir
	MiniDFS > fetch2 dir/file_name save_path
	
	# delete file
        MiniDFS > rm file_id
  
	# list meta-info of Chunks
	MiniDFS > meta_chunks

	# list meta-info of Replicas
	MiniDFS > meta_replicas

	# check file integrity
	MiniDFS > check

	# recover broken chunks
	MiniDFS > recover_chunks

	# recover failed servers
	MiniDFS > recover_servers

	# format dfs (clear up all files)
	MiniDFS > namenode_format
	# exit
	MiniDFS > quit
	```

## Example
```bash
python main.py

MiniDFS > ls

MiniDFS > ls2

# upload file
MiniDFS > put samples.txt

# make dir
MiniDFS > mkdir large_file

# put using filename
MiniDFS > put2 sample2.txt large_file


# read using file id
MiniDFS > read 0 0 10

# read using dir/name
MiniDFS > read2 sample.txt 0 100

# download using file id
MiniDFS > fetch 0 filename

MiniDFS > fetch2 large_file/sample2.txt filename


# check file tree
MiniDFS > ls

MiniDFS > ls2

# exit
MiniDFS > quit


```
