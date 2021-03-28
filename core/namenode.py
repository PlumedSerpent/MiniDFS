from .common import *
from .tree import FileTree
import os
import shutil
class NameNode(threading.Thread):
    """
    Name Server，handle instructions and manage data servers
    Client can use `ls, read, fetch` cmds.
    """
    def __init__(self, name, gconf):
        super(NameNode, self).__init__(name=name)
        self.gconf = gconf # global parameters
        self.metas = None
        self.id_chunk_map = None # file id -> chunk, eg. {0: ['0-part-0'], 1: ['1-part-0']}
        self.id_file_map = None # file id -> name, eg. {0: ('README.md', 1395), 1: ('mini_dfs.py', 14603)}
        self.chunk_server_map = None # chunk -> data servers, eg. {'0-part-0': [0, 1, 2], '1-part-0': [0, 1, 2]}
        self.last_file_id = -1 # eg. 1
        self.last_data_server_id = -1 # eg. 2
        self.tree = None # dir tree
        self.load_hole=[]
        self.load_meta()

    def run(self):
        gconf = self.gconf
        while True:
            # waiting for cmds
            gconf.name_event.wait()

            if gconf.cmd_flag:
                if gconf.cmd_type in [COMMAND.put, COMMAND.put2]:
                    self.put()
                elif gconf.cmd_type in [COMMAND.read, COMMAND.read2]:
                    self.read()
                elif gconf.cmd_type in [COMMAND.fetch, COMMAND.fetch2]:
                    self.fetch()
                elif gconf.cmd_type in [COMMAND.ls, COMMAND.ls2]:
                    self.ls()
                elif gconf.cmd_type == COMMAND.mkdir:
                    self.tree.insert(gconf.file_dir)
                    self.gconf.mkdir_event.set()
                elif gconf.cmd_type in [COMMAND.meta_chunks,COMMAND.meta_replicas]:
                    self.meta()
                elif gconf.cmd_type in [COMMAND.namenode_format]:
                    self.format()
                elif gconf.cmd_type in [COMMAND.check]:
                    self.check()
                elif gconf.cmd_type in [COMMAND.recover_chunks,COMMAND.recover_servers]:
                    self.recover()
                elif gconf.cmd_type in [COMMAND.rm]:
                    self.rm()

                else:
                    pass
            gconf.name_event.clear()

    def load_meta(self):
        """load Name Node Meta Data"""

        if not os.path.isfile(NAME_NODE_META_PATH):
            self.metas = {
                'id_chunk_map': {},
                'id_file_map': {},
                'chunk_server_map': {},
                'last_file_id': -1,
                'last_data_server_id': -1,
                'tree': FileTree(),
                'load_hole':{'start':0,'len':0}
            }
        else:
            with open(NAME_NODE_META_PATH, 'rb') as f:
                self.metas = pickle.load(f)
        self.id_chunk_map = self.metas['id_chunk_map']
        self.id_file_map = self.metas['id_file_map']
        self.chunk_server_map = self.metas['chunk_server_map']
        self.last_file_id = self.metas['last_file_id']
        self.last_data_server_id = self.metas['last_data_server_id']
        self.load_hole = self.metas['load_hole']
        self.tree = self.metas['tree']
        

    def update_meta(self):
        """update Name Node Meta Data after put"""

        with open(NAME_NODE_META_PATH, 'wb') as f:
            self.metas['last_file_id'] = self.last_file_id
            self.metas['last_data_server_id'] = self.last_data_server_id
            self.metas['tree']=self.tree
            pickle.dump(self.metas, f)

    def ls(self):
        """ls print meta data info"""
        print('total {} files in MiniDFS.'.format(len(self.id_file_map)))
        if self.gconf.cmd_type == COMMAND.ls2:
            self.tree.view_new(self.id_file_map)
        else:
            for file_id, (file_name, file_len) in self.id_file_map.items():
                print(LS_PATTERN % (file_id, file_name, file_len))
        self.gconf.ls_event.set()
    def meta(self):
        """ls print meta data info"""
        print("Checking meta infomation!")
        if self.gconf.cmd_type == COMMAND.meta_chunks:
            for fileid in self.id_chunk_map:
                print("{} split into {}".format(fileid,self.metas['id_chunk_map'][fileid]))
        else:
            for fileid in self.id_chunk_map:
                for chunkid in self.metas['id_chunk_map'][fileid]:   
                    print("{}:{}".format(chunkid,self.metas['chunk_server_map'][chunkid]),end="\t")
                print("\n")
        self.gconf.meta_event.set()
    def recover(self):
        if self.gconf.cmd_type == COMMAND.recover_chunks:
            error_list={}
            for fileid in self.id_chunk_map:
                for chunkid in self.id_chunk_map[fileid]:

                    md5list=[]
                    for server in self.chunk_server_map[chunkid]:
                        if os.path.exists('./dfs/datanode{}/{}'.format(server,chunkid)):
                            md5value=md5sum('./dfs/datanode{}/{}'.format(server,chunkid))
                            md5list.append(md5value)
                        else:
                            md5value="File Chunks Lost!"
                            print(md5value,end=" ")
                            md5list.append(md5value)
                    if len(set(md5list))!=1:
                        md_appear = dict((md, md5list.count(md)) for md in md5list)
                        
                        if max(md_appear.values())>1:
                            # 少数服从多数
                            for k,v in md_appear.items():
                                if v==max(md_appear.values()):
                                    truemd=k
                            for i in range(len(md5list)):
                                if md5list[i]!=truemd:
                                    error_list[chunkid]=self.chunk_server_map[chunkid][i]
                                    break
                        else:
                            # 损坏超过半数，重新计算md5sum
                            print("More than half replicas of {} has been broken, please re-put the file {} . ".format(chunkid,self.id_file_map[fileid]))
                            continue
            for chunkid,serverid in error_list.items():
                fileid=chunkid.split("-")[0]
                filename,file_length=self.id_file_map[int(fileid)]
                chunkorder=chunkid.split("-")[-1]
                chunks = int(math.ceil(float(file_length) / CHUNK_SIZE))
                size_in_chunk = CHUNK_SIZE if int(chunkorder) < chunks - 1 else file_length % CHUNK_SIZE
                if serverid not in self.gconf.server_chunk_map:
                    self.gconf.server_chunk_map[serverid] = []
                copyfrom=0
                for copyid in self.chunk_server_map[chunkid]:
                    if copyid!=serverid:
                        copyfrom=copyid
                        break
                self.gconf.server_chunk_map[serverid].append({chunkid:copyfrom})
            for data_event in self.gconf.data_events:
                data_event.set()
        
        else:
            downserver=-1
            for i in range(NUM_DATA_SERVER):
                if not os.path.isdir("dfs/datanode%d"%i):

                    downserver=i
                    break
                elif not os.listdir("dfs/datanode%d"%i):
                     for  chunkid in self.chunk_server_map:
                        if i in self.chunk_server_map[chunkid]:
                            downserver=i
                            break
           
            if downserver==-1:
                print("No server down.")
                for data_event in self.gconf.data_events:
                    data_event.set()
                return 
            if downserver not in self.gconf.server_chunk_map:
                    self.gconf.server_chunk_map[downserver] = []
            for  chunkid in self.chunk_server_map:
                if downserver in self.chunk_server_map[chunkid]:
                    copyfrom=0
                    for copyid in self.chunk_server_map[chunkid]:
                        if copyid!=downserver:
                            copyfrom=copyid
                            break
                    self.gconf.server_chunk_map[downserver].append({chunkid:copyfrom})
            for data_event in self.gconf.data_events:
                data_event.set()  
            
    def rm(self):
        gconf = self.gconf
        file_id = gconf.file_id
        all_chunk=self.id_chunk_map[file_id]    
        total_chunk= len(all_chunk)*NUM_REPLICATION
        reminder=total_chunk%NUM_DATA_SERVER
        fst_server=self.chunk_server_map[all_chunk[0]][0]
        self.load_hole['start']=fst_server
        self.load_hole['len']=total_chunk

        for chunkid in all_chunk:
            for serverid in self.chunk_server_map[chunkid]:

                if serverid not in self.gconf.server_chunk_map:
                    self.gconf.server_chunk_map[serverid] = []
                
                self.gconf.server_chunk_map[serverid].append(chunkid)
            self.chunk_server_map.pop(chunkid)
        self.tree.rm(file_id)
        self.id_file_map.pop(file_id)
        self.id_chunk_map.pop(file_id)
        self.update_meta()
        for data_event in self.gconf.data_events:
            data_event.set()  
        

    def check(self):
        for i in range(NUM_DATA_SERVER):
            if not os.path.isdir("dfs/datanode%d"%i):
                print("Datanode {} down! Recover by 'recover_servers'".format(i))
                self.gconf.check_event.set()
                return
            if not os.listdir("dfs/datanode%d"%i):
                     for  chunkid in self.chunk_server_map:
                        if i in self.chunk_server_map[chunkid]:
                            print("Datanode {} down! Recover by 'recover_servers'".format(i))
                            self.gconf.check_event.set()
                            return

        print("Checking chunks consistency:")
        for fileid in self.id_chunk_map:
            for chunkid in self.id_chunk_map[fileid]:
                print(chunkid,end=" ")
                md5list=[]
                for server in self.chunk_server_map[chunkid]:
                    if os.path.exists('./dfs/datanode{}/{}'.format(server,chunkid)):
                        md5value=md5sum('./dfs/datanode{}/{}'.format(server,chunkid))
                        print(md5value,end=" ")
                        md5list.append(md5value)
                    else:
                        md5value="File Chunks Lost!"
                        print(md5value,end=" ")
                        md5list.append(md5value)
                if len(set(md5list))==1:
                    print("SAME")
                else:
                    print('DIFF FOUND! Recover by "recover_chunks"')
        self.gconf.check_event.set()

    def format(self):
        print("This operation will clean-up all your data. Are you sure?(y or n)")
        verify=input()
        if (verify=="y"):
            shutil.rmtree("./dfs/namenode")

            os.mkdir("./dfs/namenode")
            self.id_chunk_map.clear()
            self.id_chunk_map.clear()
            self.id_file_map.clear()
            self.chunk_server_map.clear()
            self.last_file_id= -1
            self.last_data_server_id=-1
            self.load_hole['start']=0
            self.load_hole['len']=0
            self.tree= FileTree()
            self.gconf.server_chunk_map = {}
            self.update_meta()

            self.gconf.file_id = self.last_file_id
            for data_event in self.gconf.data_events:
                data_event.set()

        else:
            print("Invalid choice.")
            for main_event in self.gconf.main_events:

                main_event.set()


    def put(self):
        """split input file into chunk, then sent to differenct chunks"""
        try:
            in_path = self.gconf.file_path

            file_name = in_path.split('/')[-1]
            self.last_file_id += 1
            # update file tree
            if self.gconf.cmd_type == COMMAND.put2:
                dir = self.gconf.put_savepath
                if dir[0] == '/': dir = dir[1:]
                if dir[-1] == '/': dir = dir[:-1]
                self.tree.insert(dir, self.last_file_id)
            else:
                
                self.tree.add(self.last_file_id)
                

            #server_id = (self.last_data_server_id + 1) % NUM_REPLICATION
            
            server_id = (self.last_data_server_id + 1) % NUM_DATA_SERVER
            if(self.load_hole['len']!=0):
                server_id=self.load_hole['start']

            file_length = os.path.getsize(in_path)

            chunks = int(math.ceil(float(file_length) / CHUNK_SIZE))
            
            # generate chunk, add into <id, chunk> mapping
            self.id_chunk_map[self.last_file_id] = [CHUNK_PATTERN % (self.last_file_id, i) for i in range(chunks)]
            self.id_file_map[self.last_file_id] = (file_name, file_length)
            put_count=chunks*NUM_REPLICATION
            for i, chunk in enumerate(self.id_chunk_map[self.last_file_id]):
                self.chunk_server_map[chunk] = []
                # copy to 4 data nodes
                for j in range(NUM_REPLICATION):
                    
                    assign_server = (server_id + j) % NUM_DATA_SERVER
                    self.chunk_server_map[chunk].append(assign_server)

                    # add chunk-server info to global variable
                    size_in_chunk = CHUNK_SIZE if i < chunks - 1 else file_length % CHUNK_SIZE
                    if assign_server not in self.gconf.server_chunk_map:
                        self.gconf.server_chunk_map[assign_server] = []
                    self.gconf.server_chunk_map[assign_server].append((chunk, CHUNK_SIZE * i, size_in_chunk))
                server_id = (server_id + NUM_REPLICATION) % NUM_DATA_SERVER

            self.last_data_server_id = (server_id - 1) % NUM_DATA_SERVER
            self.load_hole['start']=0
            self.load_hole['len']=0
            
            self.update_meta()
            #print(self.tree.tree)

            self.gconf.file_id = self.last_file_id
            for data_event in self.gconf.data_events:
                data_event.set()
        except Exception as e: 
            print(e)
            for main_event in self.gconf.main_events:

                main_event.set()

    def read(self):
        """assign read mission to each data node"""

        gconf = self.gconf
        file_id = gconf.file_id
        read_offset = gconf.read_offset
        read_count = gconf.read_count

        # find file_id
        file_dir = gconf.file_dir
        if self.gconf.cmd_type == COMMAND.read2:
            file_id = self.tree.get_id_by_path(file_dir, self.id_file_map)
            gconf.file_id = file_id
            if file_id < 0:
                print('No such file:', file_dir)
                gconf.read_event.set()
                return False

        if file_id not in self.id_file_map:
            print('No such file with id =', file_id)
            gconf.read_event.set()
        elif read_offset < 0 or read_count < 0:
            print('Read offset or count cannot less than 0')
            gconf.read_event.set()
        elif (read_offset + read_count) > self.id_file_map[file_id][1]:
            print('The expected reading exceeds the file, file size:', self.id_file_map[file_id][1])
            gconf.read_event.set()
        else:
            start_chunk = int(math.floor(read_offset / CHUNK_SIZE))
            space_left_in_chunk = (start_chunk + 1) * CHUNK_SIZE - read_offset

            if space_left_in_chunk < read_count:
                print('Cannot read across chunks')
                gconf.read_event.set()
            else:
                # randomly select a data server to read chunk
                read_server_candidates = self.chunk_server_map[CHUNK_PATTERN % (file_id, start_chunk)]
                read_server_id = choice(read_server_candidates)
                gconf.read_chunk = CHUNK_PATTERN % (file_id, start_chunk)
                gconf.read_offset = read_offset - start_chunk * CHUNK_SIZE
                gconf.data_events[read_server_id].set()
                return True

        return False

    def fetch(self):
        """assign download mission"""
        try:
            gconf = self.gconf
            file_id = gconf.file_id

            # find file_id
            file_dir = gconf.file_dir
            if self.gconf.cmd_type == COMMAND.fetch2:
                file_id = self.tree.get_id_by_path(file_dir, self.id_file_map)
                gconf.file_id = file_id
                if file_id < 0:
                    gconf.fetch_chunks = -1
                    print('No such file:', file_dir)
                    for data_event in gconf.data_events:
                        data_event.set()
                    return None

            if file_id not in self.id_file_map:
                gconf.fetch_chunks = -1
                print('No such file with id =', file_id)
            else:
                print(self.chunk_server_map)
                file_chunks = self.id_chunk_map[file_id]
                # print(self.id_chunk_map)
                gconf.fetch_chunks = len(file_chunks)
                # get file's data server
                for chunk in file_chunks:
                    gconf.fetch_servers.append(self.chunk_server_map[chunk][0])
                for data_event in gconf.data_events:
                    data_event.set()
                return True

            for data_event in gconf.data_events:
                data_event.set()
            # print(gconf.fetch_chunks)
        except Exception as e:
            print(e)
            for data_event in gconf.data_events:
                data_event.set()
        return None
 